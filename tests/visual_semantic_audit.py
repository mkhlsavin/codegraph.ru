#!/usr/bin/env python3
"""Capture and compare Story 1113 semantic and visual evidence for every HTML route.

The runner is intentionally independent from application JavaScript. It opens every
generated public page in deterministic desktop and mobile contexts, records structural
and accessibility signals, and saves a screenshot plus a machine-readable manifest.
Use ``--enforce`` for closure evidence and ``--compare-to`` for migration parity.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from playwright.async_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Route,
    async_playwright,
)

LANDING_ROOT = Path(__file__).resolve().parents[1]
PROFILES: dict[str, dict[str, Any]] = {
    "desktop": {
        "context": {"viewport": {"width": 1440, "height": 900}, "is_mobile": False},
        "media": "screen",
    },
    "mobile": {
        "context": {"viewport": {"width": 390, "height": 844}, "is_mobile": True},
        "media": "screen",
    },
    "tablet": {
        "context": {"viewport": {"width": 768, "height": 1024}, "is_mobile": True},
        "media": "screen",
    },
    "reduced-motion": {
        "context": {
            "viewport": {"width": 1440, "height": 900},
            "is_mobile": False,
            "reduced_motion": "reduce",
        },
        "media": "screen",
    },
    "print": {
        "context": {"viewport": {"width": 1200, "height": 1600}, "is_mobile": False},
        "media": "print",
    },
}
HARD_FIELDS = (
    "status",
    "lang",
    "title",
    "description",
    "buyer_question",
    "main_buyer_question",
    "canonical",
    "canonical_count",
    "h1_count",
    "main_count",
    "inline_styles",
    "style_blocks",
    "horizontal_overflow",
    "broken_images",
    "missing_image_dimensions",
    "missing_alt",
    "unnamed_buttons",
    "unnamed_links",
    "unlabelled_controls",
    "duplicate_ids",
    "heading_level_jumps",
    "json_ld_errors",
    "webpage_schema_parity",
    "og_title",
    "og_description",
    "twitter_title",
    "twitter_description",
    "csp",
    "remote_font_links",
    "active_motion",
    "h1_contrast_ratio",
    "print_shell_chrome",
    "print_form_controls",
    "data_density",
    "top_level_h2",
    "wide_diagrams_without_strategy",
    "drawer_focus_inside",
    "drawer_background_inert",
    "drawer_focus_returned",
    "active_nav_visual",
    "editorial_card_shadows",
    "diagram_text_contrast_light",
    "diagram_text_contrast_dark",
    "diagram_edge_contrast",
    "diagram_active_node_count",
    "diagram_unclassified_text",
    "overlapping_elements",
    "touching_text_blocks",
    "article_zero_paragraph_gaps",
    "same_surface_section_gap",
    "new_surface_heading_inset",
    "same_surface_continuation_inset",
    "touch_target_min",
    "hero_to_first_section_gap",
    "card_first_child_offset",
    "resource_shell_inner_padding",
    "faq_item_gap",
    "freshness_note_count",
    "freshness_min_gap",
)


def _install_windows_socketpair_fallback() -> None:
    """Keep asyncio usable when a local proxy exhausts Windows dynamic TCP ports.

    The standard Windows ``socketpair`` fallback asks the OS for an ephemeral port.
    Some VPN/proxy drivers reserve that entire range, producing WinError 10055 before
    Playwright starts. On that exact error only, use a free loopback port below the
    dynamic range for the event-loop wakeup pair. Linux and healthy Windows hosts keep
    the standard-library implementation unchanged.
    """
    if sys.platform != "win32":
        return
    original = socket.socketpair

    def resilient_socketpair(
        family: int = socket.AF_INET,
        type: int = socket.SOCK_STREAM,
        proto: int = 0,
    ) -> tuple[socket.socket, socket.socket]:
        try:
            return original(family, type, proto)
        except OSError as error:
            if getattr(error, "winerror", None) != 10055 or family != socket.AF_INET:
                raise

        listener = socket.socket(family, type, proto)
        client = socket.socket(family, type, proto)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            first_port = 20_000 + (os.getpid() % 10_000)
            candidates = [*range(first_port, 30_000), *range(20_000, first_port)]
            for port in candidates:
                try:
                    listener.bind(("127.0.0.1", port))
                    break
                except OSError:
                    continue
            else:  # pragma: no cover - host resource exhaustion
                raise OSError("no loopback port available for asyncio socketpair")
            listener.listen(1)
            client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            for port in reversed(candidates):
                if port == listener.getsockname()[1]:
                    continue
                try:
                    client.bind(("127.0.0.1", port))
                    break
                except OSError:
                    continue
            else:  # pragma: no cover - host resource exhaustion
                raise OSError(
                    "no client loopback port available for asyncio socketpair"
                )
            client.setblocking(False)
            try:
                client.connect(listener.getsockname())
            except (BlockingIOError, InterruptedError):
                pass
            server, _address = listener.accept()
            client.setblocking(True)
            return server, client
        except Exception:
            client.close()
            raise
        finally:
            listener.close()

    socket.socketpair = resilient_socketpair


def _routes() -> list[str]:
    """Return every public HTML projection except search-engine ownership tokens."""
    return sorted(
        path.relative_to(LANDING_ROOT).as_posix()
        for path in LANDING_ROOT.rglob("*.html")
        if "node_modules" not in path.parts
        and "templates" not in path.relative_to(LANDING_ROOT).parts
        and not path.name.startswith("yandex_")
    )


def _screenshot_name(profile: str, route: str) -> str:
    """Return a stable flat screenshot name for a route/profile pair."""
    safe_route = re.sub(r"[^A-Za-z0-9._-]+", "__", route)
    return f"{profile}__{safe_route}.jpg"


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a generated evidence file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _serve_local_request(route: Route, *, base_url: str) -> None:
    """Fulfil same-origin audit requests from the bounded landing directory.

    Browser routing keeps the evidence run deterministic and avoids consuming a TCP
    client port for every page when a host VPN has exhausted the Windows dynamic range.
    Requests outside the configured audit origin remain blocked, and resolved paths must
    stay below ``LANDING_ROOT``.
    """
    request_url = route.request.url
    if request_url.startswith(("data:", "blob:")):
        await route.continue_()
        return
    if not request_url.startswith(base_url.rstrip("/") + "/"):
        await route.abort()
        return

    relative_url = unquote(urlparse(request_url).path).lstrip("/")
    candidate = (LANDING_ROOT / relative_url).resolve()
    try:
        candidate.relative_to(LANDING_ROOT.resolve())
    except ValueError:
        await route.fulfill(status=403, body="Forbidden")
        return
    if candidate.is_dir():
        candidate /= "index.html"
    if not candidate.is_file():
        await route.fulfill(status=404, body="Not found")
        return

    content_type, _encoding = mimetypes.guess_type(candidate.name)
    await route.fulfill(
        status=200,
        path=str(candidate),
        content_type=content_type or "application/octet-stream",
    )


async def _evaluate_after_navigation(
    page: Page,
    expression: str,
    argument: Any = None,
) -> Any:
    """Retry evaluation after a bounded same-page redirect finishes loading."""
    for attempt in range(3):
        try:
            return await page.evaluate(expression, argument)
        except PlaywrightError as error:
            navigation_race = "Execution context was destroyed" in str(error)
            if not navigation_race or attempt == 2:
                raise
            await page.wait_for_load_state("domcontentloaded", timeout=5_000)
    raise AssertionError("unreachable navigation retry state")


async def _inspect_route(
    context: BrowserContext,
    *,
    base_url: str,
    output: Path,
    profile: str,
    route: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    """Inspect one route and capture its deterministic visual projection."""
    async with semaphore:
        page = await context.new_page()
        console_errors: list[str] = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text)
                if message.type == "error"
                and not message.text.startswith("Failed to load resource:")
                else None
            ),
        )
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: (
                console_errors.append(f"requestfailed:{request.url}:{request.failure}")
                if request.url.startswith(base_url.rstrip("/"))
                and request.failure != "net::ERR_ABORTED"
                else None
            ),
        )
        result: dict[str, Any] = {"profile": profile, "route": route}
        try:
            response = await page.goto(
                f"{base_url.rstrip('/')}/{route}",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            await _evaluate_after_navigation(
                page,
                """async () => {
                  if (document.fonts && document.fonts.ready) await document.fonts.ready;
                }""",
            )
            await page.wait_for_timeout(100)
            if profile == "print":
                await page.emulate_media(media="print")
            result.update(
                await _evaluate_after_navigation(
                    page,
                    """async (profile) => {
                      const headings = [...document.querySelectorAll('main h1,main h2,main h3,main h4,main h5,main h6')]
                        .map((node) => Number(node.tagName.slice(1)));
                      const jsonLdErrors = [];
                      const webPages = [];
                      document.querySelectorAll('script[type="application/ld+json"]').forEach((node, index) => {
                        try {
                          const payload = JSON.parse(node.textContent);
                          if (payload && payload['@type'] === 'WebPage') webPages.push(payload);
                        }
                        catch (error) { jsonLdErrors.push(`${index}:${error.message}`); }
                      });
                      const title = document.title.trim();
                      const description = document.querySelector('meta[name="description"]')?.content?.trim() || '';
                      const normalizeSemanticText = (value) => String(value || '')
                        .replace(/\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim();
                      const buyerQuestion = document.querySelector('meta[name="cg:buyer-question"]')?.content?.trim() || '';
                      const mainBuyerQuestion = document.querySelector('main')?.dataset?.buyerQuestion?.trim() || '';
                      const ids = [...document.querySelectorAll('[id]')].map((node) => node.id).filter(Boolean);
                      const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
                      const hasAccessibleName = (node) => Boolean(
                        node.getAttribute('aria-label')?.trim()
                        || node.getAttribute('aria-labelledby')?.trim()
                        || node.getAttribute('title')?.trim()
                        || node.textContent?.trim()
                        || node.querySelector('img[alt]')?.getAttribute('alt')?.trim()
                      );
                      const hasLabel = (control) => Boolean(
                        control.getAttribute('aria-label')?.trim()
                        || control.getAttribute('aria-labelledby')?.trim()
                        || (control.id && document.querySelector(`label[for="${CSS.escape(control.id)}"]`))
                        || control.closest('label')
                      );
                      const isVisible = (node) => {
                        const style = getComputedStyle(node);
                        const box = node.getBoundingClientRect();
                        return style.display !== 'none'
                          && style.visibility !== 'hidden'
                          && Number.parseFloat(style.opacity || '1') > 0
                          && box.width > 0
                          && box.height > 0;
                      };
                      const rgb = (value) => {
                        const match = value.match(/rgba?\\(([^)]+)\\)/);
                        if (match) {
                          const parts = match[1].split(',').map((part) => Number.parseFloat(part));
                          return {r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1};
                        }
                        const canvas = document.createElement('canvas');
                        canvas.width = 1;
                        canvas.height = 1;
                        const context = canvas.getContext('2d');
                        context.clearRect(0, 0, 1, 1);
                        context.fillStyle = value;
                        context.fillRect(0, 0, 1, 1);
                        const data = context.getImageData(0, 0, 1, 1).data;
                        return {r: data[0], g: data[1], b: data[2], a: data[3] / 255};
                      };
                      const luminance = (color) => {
                        const channels = [color.r, color.g, color.b].map((value) => {
                          const normalized = value / 255;
                          return normalized <= 0.03928
                            ? normalized / 12.92
                            : ((normalized + 0.055) / 1.055) ** 2.4;
                        });
                        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
                      };
                      const h1 = document.querySelector('h1');
                      let backgroundNode = h1;
                      let background = null;
                      while (backgroundNode && !background) {
                        const candidate = rgb(getComputedStyle(backgroundNode).backgroundColor);
                        if (candidate && candidate.a > 0.1) background = candidate;
                        backgroundNode = backgroundNode.parentElement;
                      }
                      const foreground = h1 ? rgb(getComputedStyle(h1).color) : null;
                      const contrast = foreground && background
                        ? (() => {
                            const first = luminance(foreground);
                            const second = luminance(background);
                            return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
                          })()
                        : 0;
                      const activeMotion = profile === 'reduced-motion'
                        ? [...document.querySelectorAll('body *')].filter((node) => {
                            const style = getComputedStyle(node);
                            const seconds = (value) => value.split(',').some((part) => {
                              const item = part.trim();
                              return item.endsWith('ms')
                                ? Number.parseFloat(item) > 20
                                : Number.parseFloat(item) > 0.02;
                            });
                            return seconds(style.animationDuration) || seconds(style.transitionDuration);
                          }).length
                        : 0;
                      const signature = [...document.querySelectorAll(
                        'body > header, main, body > footer, h1, h2, table, form, nav'
                      )].slice(0, 40).map((node) => {
                        const box = node.getBoundingClientRect();
                        const style = getComputedStyle(node);
                        return {
                          tag: node.tagName,
                          class: node.className || '',
                          box: [box.x, box.y, box.width, box.height].map((value) => Math.round(value * 10) / 10),
                          display: style.display,
                          position: style.position,
                          color: style.color,
                          background: style.backgroundColor,
                          fontSize: style.fontSize,
                        };
                      });
                      const diagrams = [...document.querySelectorAll('[data-product-diagram]')];
                      const wideDiagrams = diagrams.filter((figure) => {
                        const svg = figure.querySelector('svg');
                        const viewBox = svg?.getAttribute('viewBox')?.trim().split(/\\s+/).map(Number);
                        return viewBox && viewBox.length === 4 && viewBox[2] >= 760;
                      });
                      const diagramMinTextPx = wideDiagrams.length
                        ? Math.min(...wideDiagrams.flatMap((figure) => {
                            const svg = figure.querySelector('svg');
                            const viewBox = svg.getAttribute('viewBox').trim().split(/\\s+/).map(Number);
                            const scale = svg.getBoundingClientRect().width / viewBox[2];
                            return [...svg.querySelectorAll('text')].map((node) => {
                              const size = Number.parseFloat(node.getAttribute('font-size') || getComputedStyle(node).fontSize || '0');
                              return Math.round(size * scale * 100) / 100;
                            });
                          }).filter((value) => value > 0))
                        : 0;
                      const contrastRatio = (foregroundColor, backgroundColor) => {
                        if (!foregroundColor || !backgroundColor || foregroundColor.a < 0.1 || backgroundColor.a < 0.1) {
                          return 0;
                        }
                        const first = luminance(foregroundColor);
                        const second = luminance(backgroundColor);
                        return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
                      };
                      const measureDiagrams = () => {
                        const measurements = [];
                        let activeNodeCount = 0;
                        let unclassifiedText = 0;
                        diagrams.forEach((figure) => {
                          const svg = figure.querySelector('svg');
                          if (!svg) return;
                          const surface = rgb(getComputedStyle(svg.parentElement || figure).backgroundColor);
                          const activeNodes = [...svg.querySelectorAll('rect.cg-diagram-node-active')];
                          activeNodeCount += activeNodes.length;
                          activeNodes.forEach((node) => {
                            const backgroundColor = rgb(getComputedStyle(node).fill);
                            const group = node.parentElement;
                            [...(group?.querySelectorAll('text.cg-diagram-title-active, text.cg-diagram-body-active') || [])]
                              .forEach((textNode) => {
                                measurements.push(contrastRatio(rgb(getComputedStyle(textNode).fill), backgroundColor));
                              });
                          });
                          [...svg.querySelectorAll('text')].forEach((textNode) => {
                            const classes = new Set(textNode.classList);
                            if (![
                              'cg-diagram-text',
                              'cg-diagram-title',
                              'cg-diagram-body',
                              'cg-diagram-title-active',
                              'cg-diagram-body-active',
                            ].some((name) => classes.has(name))) {
                              unclassifiedText += 1;
                            }
                          });
                          [...svg.querySelectorAll('path.cg-diagram-edge, path.cg-diagram-edge-active')].forEach((edge) => {
                            measurements.push({
                              edge: contrastRatio(rgb(getComputedStyle(edge).stroke), surface),
                              active: edge.classList.contains('cg-diagram-edge-active'),
                            });
                          });
                        });
                        const textValues = measurements.filter((value) => typeof value === 'number');
                        const edgeValues = measurements.filter((value) => typeof value === 'object');
                        return {
                          textContrast: textValues.length ? Math.min(...textValues) : 0,
                          edgeContrast: edgeValues.length
                            ? Math.min(...edgeValues.map((value) => value.edge))
                            : 0,
                          activeNodeCount,
                          unclassifiedText,
                        };
                      };
                      const previousTheme = document.documentElement.getAttribute('data-theme');
                      document.documentElement.setAttribute('data-theme', 'light');
                      const diagramLight = measureDiagrams();
                      document.documentElement.setAttribute('data-theme', 'dark');
                      const diagramDark = measureDiagrams();
                      if (previousTheme === null) {
                        document.documentElement.removeAttribute('data-theme');
                      } else {
                        document.documentElement.setAttribute('data-theme', previousTheme);
                      }
                      const activePageLink = document.querySelector('.cg-nav-link[aria-current="page"]');
                      const activePageStyle = activePageLink ? getComputedStyle(activePageLink) : null;
                      const drawerToggle = document.querySelector('[data-mobile-menu-toggle]');
                      const drawer = document.querySelector('[data-mobile-nav]');
                      let drawerFocusInside = null;
                      let drawerBackgroundInert = null;
                      let drawerFocusReturned = null;
                      if (profile === 'mobile' && drawerToggle && drawer) {
                        drawerToggle.focus();
                        drawerToggle.click();
                        await new Promise((resolve) => requestAnimationFrame(resolve));
                        drawerFocusInside = drawer.contains(document.activeElement);
                        drawerBackgroundInert = Boolean(document.querySelector('main')?.inert && document.querySelector('footer')?.inert);
                        drawer.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
                        await new Promise((resolve) => requestAnimationFrame(resolve));
                        drawerFocusReturned = document.activeElement === drawerToggle;
                      }
                      const boxGap = (first, second) => Math.round((second.top - first.bottom) * 10) / 10;
                      const flowChildren = (node) => [...(node?.children || [])].filter((child) => {
                        const style = getComputedStyle(child);
                        return isVisible(child) && !['absolute', 'fixed', 'sticky'].includes(style.position);
                      });
                      const overlap = (first, second) => Math.max(
                        0,
                        Math.min(first.right, second.right) - Math.max(first.left, second.left),
                      ) * Math.max(
                        0,
                        Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top),
                      );
                      const siblingGroups = [
                        ...[...document.querySelectorAll('main')].map((node) => flowChildren(node)),
                        ...[...document.querySelectorAll('.cg-article-section, .cg-resource-shell')]
                          .map((node) => flowChildren(node)),
                      ];
                      let overlappingElements = 0;
                      siblingGroups.forEach((group) => {
                        group.forEach((first, firstIndex) => {
                          group.slice(firstIndex + 1).forEach((second) => {
                            if (overlap(first.getBoundingClientRect(), second.getBoundingClientRect()) > 1) {
                              overlappingElements += 1;
                            }
                          });
                        });
                      });
                      const textElement = (node) => /^(H[1-6]|P|LI|STRONG|SPAN)$/.test(node.tagName);
                      let touchingTextBlocks = 0;
                      [...document.querySelectorAll('.cg-article-section, .cg-article-hero, .cg-article-fact, .cg-article-related-link')]
                        .map((node) => flowChildren(node).filter(textElement))
                        .forEach((group) => {
                          group.slice(1).forEach((node, index) => {
                            if (boxGap(group[index].getBoundingClientRect(), node.getBoundingClientRect()) < 4) {
                              touchingTextBlocks += 1;
                            }
                          });
                        });
                      let articleZeroParagraphGaps = 0;
                      [...document.querySelectorAll('.cg-article-section')].forEach((section) => {
                        const children = flowChildren(section);
                        children.slice(1).forEach((node, index) => {
                          const previous = children[index];
                          const paragraphPair = (previous.matches('p') && node.matches('p'))
                            || (previous.matches('p') && node.matches('ul, ol'))
                            || (previous.matches('ul, ol') && node.matches('p'));
                          if (paragraphPair && boxGap(previous.getBoundingClientRect(), node.getBoundingClientRect()) < 12) {
                            articleZeroParagraphGaps += 1;
                          }
                        });
                      });
                      const contentBottom = (section) => {
                        const contentRoot = section.querySelector(':scope > .cg-content-shell') || section;
                        const candidates = flowChildren(contentRoot)
                          .map((node) => node.getBoundingClientRect().bottom);
                        return candidates.length ? Math.max(...candidates) : section.getBoundingClientRect().bottom;
                      };
                      const directSections = [...document.querySelectorAll(
                        'main > section, main > .cg-page-chapter > section'
                      )];
                      let sameSurfaceSectionGap = 0;
                      const newSurfaceHeadingInsets = [];
                      let sameSurfaceContinuationInset = 0;
                      directSections.slice(1).forEach((section, index) => {
                        const previous = directSections[index];
                        const previousStyle = getComputedStyle(previous);
                        const currentStyle = getComputedStyle(section);
                        const heading = section.querySelector('h2, h3');
                        if (heading && isVisible(heading)) {
                          const inset = heading.getBoundingClientRect().top - section.getBoundingClientRect().top;
                          if (section.classList.contains('cg-section-new-surface')) {
                            newSurfaceHeadingInsets.push(inset);
                          } else if (section.classList.contains('cg-section-continuation')) {
                            sameSurfaceContinuationInset = Math.max(sameSurfaceContinuationInset, inset);
                          }
                        }
                        if (previousStyle.backgroundColor === currentStyle.backgroundColor) {
                          if (heading && isVisible(heading)) {
                            sameSurfaceSectionGap = Math.max(
                              sameSurfaceSectionGap,
                              boxGap(
                                {bottom: contentBottom(previous)},
                                heading.getBoundingClientRect(),
                              ),
                            );
                          }
                        }
                      });
                      let heroToFirstSectionGap = 0;
                      const heroCandidate = document.querySelector('main > #hero')
                        || document.querySelector('main > section:first-child');
                      const hero = heroCandidate && (
                        heroCandidate.id === 'hero'
                        || heroCandidate.querySelector('[data-visual-kind="product-preview"], [data-visual-kind="product-screen"]')
                      )
                        ? heroCandidate
                        : null;
                      const firstSection = hero?.nextElementSibling;
                      const firstSectionHeading = firstSection?.querySelector('h2, h3');
                      const heroProof = hero?.querySelector('[data-visual-kind="product-screen"], [data-visual-kind="product-preview"], .cg-product-preview') || hero;
                      if (heroProof && firstSectionHeading && isVisible(firstSectionHeading)
                        && !firstSection?.matches('.cg-whitepaper-layout')) {
                        heroToFirstSectionGap = boxGap(heroProof.getBoundingClientRect(), firstSectionHeading.getBoundingClientRect());
                      }
                      const cardOffsets = [...document.querySelectorAll('.cg-article-list-card, .cg-resource-card')]
                        .map((card) => {
                          const firstChild = flowChildren(card)[0];
                          return firstChild
                            ? firstChild.getBoundingClientRect().top - card.getBoundingClientRect().top
                            : 0;
                        });
                      const cardFirstChildOffset = cardOffsets.length ? Math.max(...cardOffsets) : 0;
                      const resourcePaddingValues = [...document.querySelectorAll('.cg-resource-intro, .cg-resource-body')]
                        .flatMap((section) => {
                          const firstChild = flowChildren(section)[0];
                          const sectionBox = section.getBoundingClientRect();
                          const childBox = firstChild?.getBoundingClientRect();
                          return firstChild && childBox
                            ? [childBox.left - sectionBox.left, sectionBox.right - childBox.right]
                            : [];
                        });
                      const resourceShellInnerPadding = resourcePaddingValues.length
                        ? Math.round(Math.min(...resourcePaddingValues) * 10) / 10
                        : 0;
                      const faqItems = [...document.querySelectorAll('.cg-faq-item')].filter(isVisible);
                      const faqGaps = faqItems.slice(1).map((item, index) => boxGap(
                        faqItems[index].getBoundingClientRect(),
                        item.getBoundingClientRect(),
                      ));
                      const faqItemGap = faqGaps.length ? Math.max(...faqGaps) : 0;
                      const freshnessNotes = [...document.querySelectorAll('[data-freshness-label]')]
                        .filter(isVisible);
                      const freshnessGaps = freshnessNotes
                        .map((note) => {
                          const previous = note.previousElementSibling;
                          return previous && isVisible(previous)
                            ? boxGap(previous.getBoundingClientRect(), note.getBoundingClientRect())
                            : 0;
                        });
                      const touchTargetSizes = [...document.querySelectorAll(
                        '.cg-button-sm, .cg-button-icon, .cg-theme-toggle, .cg-mobile-toggle, .cg-footer-social-link'
                      )]
                        .filter(isVisible)
                        .map((node) => {
                          const box = node.getBoundingClientRect();
                          return Math.min(box.width, box.height);
                        });
                      return {
                        title,
                        description,
                        buyer_question: buyerQuestion,
                        main_buyer_question: mainBuyerQuestion,
                        canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                        canonical_count: document.querySelectorAll('link[rel="canonical"]').length,
                        lang: document.documentElement.lang,
                        h1_count: document.querySelectorAll('h1').length,
                        main_count: document.querySelectorAll('main').length,
                        header_count: document.querySelectorAll('body > header').length,
                        footer_count: document.querySelectorAll('body > footer').length,
                        inline_styles: document.querySelectorAll('[style]').length,
                        style_blocks: document.querySelectorAll('style').length,
                        horizontal_overflow: Math.max(
                          0,
                          document.documentElement.scrollWidth - document.documentElement.clientWidth
                        ),
                        broken_images: [...document.images]
                          .filter((image) => image.getAttribute('src')?.trim())
                          .filter((image) => image.complete && image.naturalWidth === 0)
                          .map((image) => image.getAttribute('src')),
                        missing_image_dimensions: [...document.images]
                          .filter((image) => image.getAttribute('src')?.trim())
                          .filter((image) => !image.hasAttribute('width') || !image.hasAttribute('height'))
                          .map((image) => image.getAttribute('src')),
                        missing_alt: [...document.images].filter((image) => !image.hasAttribute('alt')).length,
                        unnamed_buttons: [...document.querySelectorAll('button')].filter(
                          (button) => !hasAccessibleName(button)
                        ).length,
                        unnamed_links: [...document.querySelectorAll('a[href]')].filter(
                          (link) => !hasAccessibleName(link)
                        ).length,
                        unlabelled_controls: [...document.querySelectorAll('input:not([type="hidden"]),select,textarea')]
                          .filter((control) => !hasLabel(control)).length,
                        duplicate_ids: duplicateIds,
                        heading_level_jumps: headings.slice(1).filter(
                          (level, index) => level - headings[index] > 1
                        ).length,
                        json_ld_errors: jsonLdErrors,
                        webpage_schema_parity: webPages.length === 1
                          && normalizeSemanticText(webPages[0].name) === normalizeSemanticText(title)
                          && normalizeSemanticText(webPages[0].description) === normalizeSemanticText(description)
                          && webPages[0].url === document.querySelector('link[rel="canonical"]')?.href,
                        webpage_schema_count: webPages.length,
                        og_title: document.querySelector('meta[property="og:title"]')?.content?.trim() || '',
                        og_description: document.querySelector('meta[property="og:description"]')?.content?.trim() || '',
                        twitter_title: document.querySelector('meta[name="twitter:title"]')?.content?.trim() || '',
                        twitter_description: document.querySelector('meta[name="twitter:description"]')?.content?.trim() || '',
                        csp: document.querySelector('meta[http-equiv="Content-Security-Policy" i]')?.content || '',
                        remote_font_links: [...document.querySelectorAll('link[href]')]
                          .map((link) => link.getAttribute('href') || '')
                          .filter((href) => href.includes('fonts.googleapis.com') || href.includes('fonts.gstatic.com')),
                        active_motion: activeMotion,
                        h1_contrast_ratio: Math.round(contrast * 100) / 100,
                        print_shell_chrome: profile === 'print'
                          ? [...document.querySelectorAll('[data-shell-header],[data-shell-footer],[data-shell-cta]')]
                              .filter(isVisible).length
                          : 0,
                        print_form_controls: profile === 'print'
                          ? [...document.querySelectorAll('form,input:not([type="hidden"]),select,textarea,button:not(.faq-question):not(.cg-faq-question)')]
                              .filter(isVisible).length
                          : 0,
                        data_density: document.body?.dataset?.density || '',
                        top_level_h2: document.querySelectorAll(
                          'main > section h2, main > .cg-page-chapter > section h2'
                        ).length,
                        wide_diagrams_without_strategy: wideDiagrams.filter(
                          (figure) => !figure.querySelector('.cg-diagram-mobile, [data-diagram-viewer], [data-screen-viewer]')
                        ).length,
                        diagram_min_text_px: diagramMinTextPx,
                        diagram_text_contrast_light: Math.round(diagramLight.textContrast * 100) / 100,
                        diagram_text_contrast_dark: Math.round(diagramDark.textContrast * 100) / 100,
                        diagram_edge_contrast: (() => {
                          const values = [diagramLight.edgeContrast, diagramDark.edgeContrast]
                            .filter((value) => value > 0);
                          return values.length ? Math.round(Math.min(...values) * 100) / 100 : 0;
                        })(),
                        diagram_active_node_count: Math.max(
                          diagramLight.activeNodeCount,
                          diagramDark.activeNodeCount
                        ),
                        diagram_unclassified_text: Math.max(
                          diagramLight.unclassifiedText,
                          diagramDark.unclassifiedText
                        ),
                        diagram_count: diagrams.length,
                        overlapping_elements: overlappingElements,
                        touching_text_blocks: touchingTextBlocks,
                        article_zero_paragraph_gaps: articleZeroParagraphGaps,
                        same_surface_section_gap: Math.round(sameSurfaceSectionGap * 10) / 10,
                        new_surface_heading_inset: newSurfaceHeadingInsets.length
                          ? Math.round(Math.min(...newSurfaceHeadingInsets) * 10) / 10
                          : 0,
                        same_surface_continuation_inset: Math.round(sameSurfaceContinuationInset * 10) / 10,
                        touch_target_min: touchTargetSizes.length
                          ? Math.round(Math.min(...touchTargetSizes) * 10) / 10
                          : 0,
                        hero_to_first_section_gap: Math.round(heroToFirstSectionGap * 10) / 10,
                        card_first_child_offset: Math.round(cardFirstChildOffset * 10) / 10,
                        resource_shell_inner_padding: resourceShellInnerPadding,
                        faq_item_gap: Math.round(faqItemGap * 10) / 10,
                        freshness_note_count: freshnessNotes.length,
                        freshness_min_gap: freshnessGaps.length
                          ? Math.round(Math.min(...freshnessGaps) * 10) / 10
                          : 0,
                        drawer_focus_inside: drawerFocusInside,
                        drawer_background_inert: drawerBackgroundInert,
                        drawer_focus_returned: drawerFocusReturned,
                        active_nav_visual: activePageLink
                          ? Boolean(
                              activePageStyle
                              && Number.parseInt(activePageStyle.fontWeight, 10) >= 600
                              && activePageStyle.boxShadow !== 'none'
                            )
                          : null,
                        editorial_card_shadows: [...document.querySelectorAll(
                          '.cg-article-list-card, .cg-article-related-link, .cg-article-fact'
                        )].filter((node) => getComputedStyle(node).boxShadow !== 'none').length,
                        stylesheet_links: [...document.querySelectorAll('link[rel="stylesheet"]')]
                          .map((link) => link.getAttribute('href')),
                        css_runtime: (() => {
                          const stylesheet = [...document.styleSheets].find((sheet) =>
                            sheet.href && sheet.href.includes('/css/tailwind.min.css')
                          );
                          const hero = document.querySelector('main > section');
                          return {
                            loaded: Boolean(stylesheet),
                            rules: stylesheet ? (() => { try { return stylesheet.cssRules.length; } catch (error) { return 0; } })() : 0,
                            hero_background: hero ? getComputedStyle(hero).backgroundColor : '',
                            hero_padding_top: hero ? getComputedStyle(hero).paddingTop : '',
                          };
                        })(),
                        render_signature: signature,
                      };
                    }""",
                    profile,
                )
            )
            result["status"] = (
                response.status
                if response
                else 200 if base_url.startswith("file:") else None
            )
            result["console_errors"] = console_errors
            screenshot = output / _screenshot_name(profile, route)
            await page.screenshot(
                path=str(screenshot),
                type="jpeg",
                quality=55,
                full_page=not route.startswith("docs/"),
                animations="disabled",
            )
            result["screenshot"] = screenshot.name
            result["screenshot_sha256"] = _sha256(screenshot)
        except Exception as error:  # pragma: no cover - runtime evidence path
            result["error"] = f"{type(error).__name__}: {error}"
        finally:
            await page.close()
        return result


def _compare(
    baseline_path: Path,
    current: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare hard semantics and render signatures with a baseline manifest."""
    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = {
        (row["profile"], row["route"]): row for row in baseline_payload["results"]
    }
    current_map = {(row["profile"], row["route"]): row for row in current}
    missing = sorted(set(baseline) - set(current_map))
    added = sorted(set(current_map) - set(baseline))
    changes: list[dict[str, Any]] = []
    for key in sorted(set(baseline) & set(current_map)):
        before = baseline[key]
        after = current_map[key]
        changed_fields = {
            field: {"before": before.get(field), "after": after.get(field)}
            for field in (*HARD_FIELDS, "render_signature")
            if before.get(field) != after.get(field)
        }
        if changed_fields:
            changes.append(
                {"profile": key[0], "route": key[1], "fields": changed_fields}
            )
    return {"missing": missing, "added": added, "changes": changes}


def _core_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return core HTTP, document, ownership, security, and canonical errors."""
    reasons: list[str] = []
    if row.get("error"):
        reasons.append(str(row["error"]))
    if row.get("status") != 200:
        reasons.append(f"status={row.get('status')}")
    if row.get("h1_count") != 1:
        reasons.append(f"h1_count={row.get('h1_count')}")
    if row.get("main_count") != 1:
        reasons.append(f"main_count={row.get('main_count')}")
    if not row.get("title") or not row.get("description"):
        reasons.append("empty title/description")
    docs_route = str(row.get("route", "")).startswith("docs/")
    if docs_route and (row.get("buyer_question") or row.get("main_buyer_question")):
        reasons.append("technical docs expose buyer-question")
    if not docs_route and (
        not row.get("buyer_question")
        or row.get("buyer_question") != row.get("main_buyer_question")
    ):
        reasons.append("buyer-question ownership mismatch")
    if "'unsafe-inline'" in str(row.get("csp", "")):
        reasons.append("CSP contains unsafe-inline")
    if row.get("remote_font_links"):
        reasons.append(f"remote_font_links={row['remote_font_links']}")
    canonical = str(row.get("canonical", ""))
    if row.get("canonical_count") != 1 or not canonical.startswith(
        "https://codegraph.ru/"
    ):
        reasons.append(
            f"canonical={row.get('canonical')} count={row.get('canonical_count')}"
        )
    if row.get("horizontal_overflow", 0) > 1:
        reasons.append(f"horizontal_overflow={row.get('horizontal_overflow')}")
    return reasons


def _collection_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return resource, console, accessibility, heading, and identity errors."""
    reasons: list[str] = []
    for field in (
        "broken_images",
        "missing_image_dimensions",
        "console_errors",
        "json_ld_errors",
    ):
        if row.get(field):
            reasons.append(f"{field}={row[field]}")
    for field in (
        "missing_alt",
        "unnamed_buttons",
        "unnamed_links",
        "unlabelled_controls",
        "heading_level_jumps",
    ):
        if row.get(field, 0):
            reasons.append(f"{field}={row[field]}")
    if row.get("duplicate_ids"):
        reasons.append(f"duplicate_ids={row['duplicate_ids']}")
    return reasons


def _metadata_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return social and WebPage metadata parity errors."""
    reasons: list[str] = []
    parity_fields = (
        ("og_title", "title", "og:title parity mismatch"),
        ("og_description", "description", "og:description parity mismatch"),
        ("twitter_title", "title", "twitter:title parity mismatch"),
        ("twitter_description", "description", "twitter:description parity mismatch"),
    )
    for actual, expected, message in parity_fields:
        if row.get(actual) != row.get(expected):
            reasons.append(message)
    if not row.get("webpage_schema_parity"):
        reasons.append(
            f"WebPage schema parity mismatch count={row.get('webpage_schema_count')}"
        )
    return reasons


def _contrast_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return heading and diagram contrast or classification errors."""
    reasons: list[str] = []
    if row.get("h1_contrast_ratio", 0) < 3:
        reasons.append(f"h1_contrast_ratio={row.get('h1_contrast_ratio')}")
    if not row.get("diagram_count", 0):
        return reasons
    thresholds = (
        ("diagram_text_contrast_light", 4.5),
        ("diagram_text_contrast_dark", 4.5),
        ("diagram_edge_contrast", 3),
    )
    for field, threshold in thresholds:
        if row.get(field, 0) < threshold:
            reasons.append(f"{field}={row.get(field)}")
    if row.get("diagram_active_node_count", 0) and row.get(
        "diagram_unclassified_text", 0
    ):
        reasons.append(
            f"diagram_unclassified_text={row.get('diagram_unclassified_text')}"
        )
    return reasons


def _public_layout_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return public-page density, hierarchy, diagram, and card errors."""
    if str(row.get("route", "")).startswith("docs/"):
        return []
    reasons: list[str] = []
    if row.get("data_density") != "expressive":
        reasons.append(f"data_density={row.get('data_density')!r}")
    if row.get("top_level_h2", 0) > 9 and row.get("route") == "index.html":
        reasons.append(f"top_level_h2={row.get('top_level_h2')}")
    if row.get("wide_diagrams_without_strategy", 0):
        reasons.append(
            f"wide_diagrams_without_strategy={row.get('wide_diagrams_without_strategy')}"
        )
    if row.get("editorial_card_shadows", 0):
        reasons.append(f"editorial_card_shadows={row.get('editorial_card_shadows')}")
    return reasons


def _drawer_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return focus-trap and inert-background errors for exercised mobile drawers."""
    if row.get("profile") != "mobile" or row.get("drawer_focus_inside") is None:
        return []
    reasons: list[str] = []
    for field in (
        "drawer_focus_inside",
        "drawer_background_inert",
        "drawer_focus_returned",
    ):
        if row.get(field) is not True:
            reasons.append(f"{field}={row.get(field)!r}")
    return reasons


def _presentation_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return screen-layout spacing, collision, freshness, and touch errors."""
    if row.get("profile") == "print":
        return []
    reasons: list[str] = []
    for field in (
        "overlapping_elements",
        "touching_text_blocks",
        "article_zero_paragraph_gaps",
    ):
        if row.get(field, 0):
            reasons.append(f"{field}={row[field]}")
    bounded_fields = (
        ("same_surface_section_gap", 0, 96),
        ("same_surface_continuation_inset", 0, 16),
        ("card_first_child_offset", 0, 28),
        ("faq_item_gap", 0, 1),
    )
    for field, _minimum, maximum in bounded_fields:
        if row.get(field, 0) > maximum:
            reasons.append(f"{field}={row[field]}")
    new_surface_inset = row.get("new_surface_heading_inset", 0)
    if new_surface_inset and not 24 <= new_surface_inset <= 48:
        reasons.append(f"new_surface_heading_inset={new_surface_inset}")
    hero_gap = row.get("hero_to_first_section_gap", 0)
    if hero_gap and not 80 <= hero_gap <= 112:
        reasons.append(f"hero_to_first_section_gap={hero_gap}")
    resource_padding = row.get("resource_shell_inner_padding", 0)
    if resource_padding and resource_padding < 20:
        reasons.append(f"resource_shell_inner_padding={resource_padding}")
    docs_route = str(row.get("route", "")).startswith("docs/")
    if not docs_route and row.get("freshness_note_count"):
        if row.get("freshness_note_count") != 1:
            reasons.append(f"freshness_note_count={row['freshness_note_count']}")
        if row.get("freshness_min_gap", 0) < 24:
            reasons.append(f"freshness_min_gap={row['freshness_min_gap']}")
    touch_target = row.get("touch_target_min", 0)
    if (
        row.get("profile") == "mobile"
        and not docs_route
        and touch_target
        and touch_target < 44
    ):
        reasons.append(f"touch_target_min={touch_target}")
    return reasons


def _profile_failure_reasons(row: dict[str, Any]) -> list[str]:
    """Return active-navigation, CSS-runtime, motion, and print-profile errors."""
    reasons: list[str] = []
    route = str(row.get("route", ""))
    if (
        row.get("active_nav_visual") is False
        and route != "index.html"
        and not route.startswith("docs/")
    ):
        reasons.append("active_nav_visual=false")
    if route == "index.html":
        css_runtime = row.get("css_runtime") or {}
        if not css_runtime.get("loaded") or not css_runtime.get("rules"):
            reasons.append(f"css_runtime_not_loaded={css_runtime}")
        if css_runtime.get("hero_background") in {
            "",
            "rgba(0, 0, 0, 0)",
            "transparent",
        }:
            reasons.append(
                f"hero_background_missing={css_runtime.get('hero_background')!r}"
            )
    if row.get("profile") == "reduced-motion" and row.get("active_motion", 0):
        reasons.append(f"active_motion={row['active_motion']}")
    if row.get("profile") != "print":
        return reasons
    if not row.get("render_signature"):
        reasons.append("empty print render signature")
    if row.get("print_shell_chrome", 0):
        reasons.append(f"print_shell_chrome={row['print_shell_chrome']}")
    if row.get("print_form_controls", 0) and not route.startswith("docs/"):
        reasons.append(f"print_form_controls={row['print_form_controls']}")
    return reasons


def _enforcement_failure_reasons(
    row: dict[str, Any],
    enforce: bool,
) -> list[str]:
    """Return fail-closed authored-style and stylesheet errors in enforce mode."""
    if not enforce:
        return []
    reasons: list[str] = []
    if row.get("inline_styles") != 0:
        reasons.append(f"inline_styles={row.get('inline_styles')}")
    if row.get("style_blocks") != 0:
        reasons.append(f"style_blocks={row.get('style_blocks')}")
    links = [
        link
        for link in (row.get("stylesheet_links") or [])
        if link and not str(link).startswith(("http://", "https://"))
    ]
    valid_tailwind_link = len(links) == 1 and str(links[0]).split("?", 1)[0].endswith(
        "css/tailwind.min.css"
    )
    if not valid_tailwind_link:
        reasons.append(f"stylesheet_links={links}")
    return reasons


def _failure_reasons(row: dict[str, Any], enforce: bool) -> list[str]:
    """Combine independent failure categories in stable reporting order."""
    return (
        _core_failure_reasons(row)
        + _collection_failure_reasons(row)
        + _metadata_failure_reasons(row)
        + _contrast_failure_reasons(row)
        + _public_layout_failure_reasons(row)
        + _drawer_failure_reasons(row)
        + _presentation_failure_reasons(row)
        + _profile_failure_reasons(row)
        + _enforcement_failure_reasons(row, enforce)
    )


def _failures(results: list[dict[str, Any]], enforce: bool) -> list[dict[str, Any]]:
    """Return fail-closed semantic, runtime and presentation defects."""
    failures: list[dict[str, Any]] = []
    for row in results:
        reasons = _failure_reasons(row, enforce)
        if reasons:
            failures.append(
                {"profile": row["profile"], "route": row["route"], "reasons": reasons}
            )
    return failures


async def _run(args: argparse.Namespace) -> int:
    """Run every configured route/profile capture and write the evidence manifest."""
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    routes = _routes()
    results: list[dict[str, Any]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        for profile, profile_options in PROFILES.items():
            context = await browser.new_context(
                **profile_options["context"],
                color_scheme="light",
            )
            await context.route(
                "**/*",
                lambda route: _serve_local_request(route, base_url=args.base_url),
            )
            semaphore = asyncio.Semaphore(args.workers)
            tasks = [
                _inspect_route(
                    context,
                    base_url=args.base_url,
                    output=output,
                    profile=profile,
                    route=route,
                    semaphore=semaphore,
                )
                for route in routes
            ]
            for index, task in enumerate(asyncio.as_completed(tasks), 1):
                results.append(await task)
                if index % 25 == 0 or index == len(tasks):
                    print(f"{profile}: {index}/{len(tasks)}", flush=True)
            await context.close()
        await browser.close()

    results.sort(key=lambda row: (row["profile"], row["route"]))
    failures = _failures(results, args.enforce)
    comparison = _compare(args.compare_to, results) if args.compare_to else None
    payload = {
        "schema_version": "story1113.visual-semantic-audit.v2",
        "label": args.label,
        "base_url": args.base_url,
        "route_count": len(routes),
        "profile_count": len(PROFILES),
        "result_count": len(results),
        "enforce": args.enforce,
        "failures": failures,
        "comparison": comparison,
        "results": results,
    }
    manifest = output / "manifest.json"
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "manifest": str(manifest),
        "route_count": len(routes),
        "result_count": len(results),
        "failure_count": len(failures),
        "comparison_changes": len(comparison["changes"]) if comparison else None,
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if failures else 0


def main() -> int:
    """Parse CLI arguments and execute the visual/semantic evidence runner."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--compare-to", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--enforce", action="store_true")
    _install_windows_socketpair_fallback()
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
