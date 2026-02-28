(() => {
    const results = [];
    const url = window.location.href;
    const pageText = document.body ? document.body.innerText.toLowerCase() : '';

    const CATEGORY_SLUGS = new Set([
        'sports',
        'nba',
        'nfl',
        'mlb',
        'nhl',
        'mls',
        'ncaa-basketball',
        'ncaa-football',
        'tennis',
        'golf',
        'boxing',
        'wwe',
        'concert',
        'theater',
        'comedy',
        'festival'
    ]);

    // ============================================================================
    // 1. UTILITIES
    // ============================================================================

    const getText = (el) => el?.textContent?.trim().replace(/\s+/g, ' ') || null;

    const extractByPattern = (text, patterns) => {
        if (!text) return null;
        for (const regex of Object.values(patterns)) {
            try {
                const match = text.match(regex);
                if (match) return match[1] || match[0];
            } catch (e) { continue; }
        }
        return null;
    };

    // ============================================================================
    // 2. PARSERS (Adapted for Ticketmaster formats)
    // ============================================================================

    const Parsers = {
        price: (text) => {
            try {
                if (!text) return null;
                let clean = text.replace(/[₹€£$]/g, '').replace(/^(INR|USD|EUR|GBP)\s*/i, '').replace(/ea\./i, '').replace(/ea/i, '').trim();

                let match = clean.match(/([\d,]+(?:\.\d{2})?)/);
                if (match) return parseFloat(match[1].replace(/,/g, ""));

                match = clean.match(/([\d.]+(?:,\d{2})?)/);
                return match ? parseFloat(match[1].replace(/\./g, "").replace(",", ".")) : null;
            } catch (e) { return null; }
        },

        date: (text) => {
            try {
                if (!text) return null;
                const clean = text.toLowerCase().trim();

                let match = text.match(/(\d{4})-(\d{2})-(\d{2})/);
                if (match) return match[0];

                match = text.match(/(?:[a-z]{3}\s*•\s*)?([a-z]{3})\s+(\d{1,2}),?\s*(\d{4})/i);
                if (match) {
                    const months = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
                    const m = months[match[1].toLowerCase().substring(0, 3)];
                    if (m) return `${match[3]}-${String(m).padStart(2, '0')}-${match[2].padStart(2, '0')}`;
                }
            } catch (e) { return null; }
            return null;
        },

        time: (text) => {
            try {
                if (!text) return null;
                const match = text.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
                if (match) {
                    let h = parseInt(match[1]);
                    if (match[3]?.toUpperCase() === 'PM' && h < 12) h += 12;
                    if (match[3]?.toUpperCase() === 'AM' && h === 12) h = 0;
                    return `${String(h).padStart(2, '0')}:${match[2]}`;
                }
            } catch (e) { return null; }
            return null;
        }
    };

    // ============================================================================
    // 3. ENRICHMENT HELPERS
    // ============================================================================

    const Enrichment = {
        pageType: () => {
            const pathname = new URL(url).pathname;
            if (pathname.endsWith('-tickets')) {
                const slug = pathname.replace(/^\/|\/$/g, '').replace('-tickets', '');
                if (CATEGORY_SLUGS.has(slug)) {
                    return 'event_category';
                }
                return 'performer';
            }
            if (url.includes('/search')) return 'search_results';
            if (pathname.match(/^\/[^\/]+-tickets\/[^\/]+\/[^\/]+\/\d+\/?$/)) return 'event_listing';
            if (url.includes('/checkout')) return 'checkout';
            return 'other';
        },
        category: () => {
            const pathname = new URL(url).pathname
                .replace(/^\/|\/$/g, '')
                .toLowerCase();

            const slug = pathname.replace('-tickets', '');
            if (CATEGORY_SLUGS.has(slug)) return 'sports';
            if (slug === 'concert') return 'concerts';
            if (slug === 'theater') return 'theater';
            if (slug === 'comedy') return 'comedy';
            if (slug === 'festival') return 'festival';
            return null;
        },
    };

    // ============================================================================
    // 4. SCRAPERS
    // ============================================================================

    const Scraper = {

        ldJson: () => {
            try {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                const found = [];

                for (const script of scripts) {
                    try {
                        const data = JSON.parse(script.textContent);
                        const graph = data["@graph"] || (Array.isArray(data) ? data : [data]);

                        for (const item of graph) {
                            const types = Array.isArray(item["@type"]) ? item["@type"] : [item["@type"] || ""];
                            if (!types.some(t => t.toLowerCase().includes("event"))) continue;

                            const startDateRaw = item.startDate || null;

                            let startDate = null;
                            let startTime = null;

                            if (startDateRaw && startDateRaw.includes("T")) {
                                const [datePart, timePart] = startDateRaw.split("T");
                                startDate = datePart;
                                startTime = timePart;
                            }

                            const location = item.location || {};
                            const address = location.address || {};
                            const geo = location.geo || {};
                            const offers = item.offers || {};

                            found.push({
                                source: "ld+json",
                                eventType: types[0] || null,
                                eventName: item.name || null,
                                date: startDate,   
                                time: startTime,
                                venue: location.name || null,
                                city: address.addressLocality || null,
                                state: address.addressRegion || null,
                                postalCode: address.postalCode || null,
                                country: address.addressCountry || null,
                                latitude: geo.latitude || null,
                                longitude: geo.longitude || null,
                                competitors: item.competitor ? item.competitor.map(c => c.name) : null,
                                lowPrice: offers.lowPrice ?? null,
                                highPrice: offers.highPrice ?? null,
                                currency: offers.priceCurrency || "USD",
                                inventoryLevel: offers.inventoryLevel ?? null,
                                eventUrl: offers.url || item.url || url
                            });
                        }
                    } catch (e) {
                    }
                }
                return found;
            } catch (e) { return []; }
        },

        ticketListings: () => {
            const collected = [];

            try {
                const container = document.querySelectorAll('[data-testid="listing-item"]');
                if (!container) return [];

                const rows = container.querySelectorAll('button[aria-label]');
                const LISTING_PATTERN = /Section\s+(.+?),\s*Row\s+(.+?),\s*(\d+)\s+to\s+(\d+)\s+tickets?\s+at\s+\$?([\d,.]+)\s+each(?:,\s*Deal Score\s+(\d+))?/i;
                rows.forEach(button => {
                    try {
                        const rowText = getText(button);
                        const aria = button.getAttribute('aria-label');
                        if (!aria) return;

                        const match = aria.match(LISTING_PATTERN);
                        if (!match) return;

                        const [
                            _,
                            section,
                            row,
                            minQty,
                            maxQty,
                            price,
                            dealScore
                        ] = match;

                        collected.push({
                            source: "dom_ticket_listing",
                            eventName: getText(document.querySelector('div[class*="EventInfoBarCTA"] p'))?.toLowerCase(),
                            pricePerTicket: Parsers.price(price),
                            section: section?.trim() || null,
                            row: row?.trim() || null,
                            quantityMin: parseInt(minQty, 10),
                            quantityMax: parseInt(maxQty, 10),
                            dealScore: dealScore ? parseInt(dealScore, 10) : null,
                            currency: "USD",
                            availabilityStatus: "available",
                            info: rowText
                        });

                    } catch (e) { console.error('Ticket row parse error', e); }
                });
                return collected;

            } catch (e) { return [] };
        },

        eventCards: () => {
            const collected = [];
            document.querySelectorAll('ul[class*="EventList__BaseEventList"]').forEach(card => {
                try {
                    const link = card.querySelector('a')?.href;
                    const text = getText(card);
                    let eventName = getText(card.querySelector('p, [data-testid="event-item-title"]'));

                    if (eventName) {
                        collected.push({
                            source: "dom_event_card",
                            url: link || url,
                            eventName: eventName.toLowerCase(),
                            date: Parsers.date(text),
                            availabilityStatus: text.toLowerCase().includes('canceled') ? 'cancelled' : 'available',
                            info: text
                        });
                    }
                } catch (e) { }
            });
            return collected;
        },
    }

    // ============================================================================
    // 5. MAIN EXECUTION
    // ============================================================================

    try {
        let scraped = [];

        scraped.push(...Scraper.ldJson());
        scraped.push(...Scraper.ticketListings());
        scraped.push(...Scraper.eventCards());

        // Fallback for empty pages (like queues or blocked pages)
        if (scraped.length === 0) {
            scraped.push({
                source: "fallback_metadata",
                url: url,
                eventName: getText(document.querySelector('p'))?.toLowerCase() || 'unknown',
                info: "No specific elements found. Check antiBot state."
            });
        }

        const meta = {
            pageType: Enrichment.pageType(),
            eventCategory: Enrichment.category(),
        };

        const seen = new Set();

        scraped.forEach(item => {
            const key = `${item.eventName}-${item.date || 'nodate'}-${item.section || 'nosection'}-${item.source}`;
            if (!seen.has(key)) {
                seen.add(key);

                results.push({
                    ...item,
                    ...meta,
                    parsedTime: Parsers.time(item.time || item.date || ''),
                });
            }
        });

    } catch (e) {
        console.error("Ticketmaster Scraper failed", e);
    }

    return results;
})();

