(() => {
    const results = [];
    const url = window.location.href;
    const pageText = document.body ? document.body.innerText.toLowerCase() : '';

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
                // TM often formats as "$125.00 ea" or includes "+ Fees"
                let clean = text.replace(/[₹€£$]/g, '').replace(/^(INR|USD|EUR|GBP)\s*/i, '').replace(/ea\./i, '').replace(/ea/i, '').trim();
                
                let match = clean.match(/([\d,]+(?:\.\d{2})?)/);
                if (match) return parseFloat(match[1].replace(/,/g, ""));
                
                match = clean.match(/([\d.]+(?:,\d{2})?)/);
                return match ? parseFloat(match[1].replace(/\./g, "").replace(",", ".")) : null;
            } catch (e) { return null; }
        },

        ticketCount: (text) => {
            try {
                if (!text) return null;
                // TM dropdowns or text often say "2 Tickets"
                return parseInt(text.match(/(\d+)\s*ticket/i)?.[1] || text.match(/^(\d+)$/)?.[1]);
            } catch (e) { return null; }
        },

        date: (text) => {
            try {
                if (!text) return null;
                const clean = text.toLowerCase().trim();
                
                // ISO format YYYY-MM-DD
                let match = text.match(/(\d{4})-(\d{2})-(\d{2})/);
                if (match) return match[0];
                
                // TM format: "Sat • Oct 24, 2026" or "Oct 24, 2026"
                match = text.match(/(?:[a-z]{3}\s*•\s*)?([a-z]{3})\s+(\d{1,2}),?\s*(\d{4})/i);
                if (match) {
                    const months = { jan:1, feb:2, mar:3, apr:4, may:5, jun:6, jul:7, aug:8, sep:9, oct:10, nov:11, dec:12 };
                    const m = months[match[1].toLowerCase().substring(0, 3)];
                    if (m) return `${match[3]}-${String(m).padStart(2,'0')}-${match[2].padStart(2,'0')}`;
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
            if (url.includes('/checkout')) return 'checkout';
            if (url.includes('queue') || pageText.includes('you are now in line')) return 'queue';
            if (url.includes('/event/')) return 'event_listing';
            if (url.includes('/search') || url.includes('/discover')) return 'search_results';
            if (url.includes('/artist/') || url.includes('/venue/')) return 'event_category';
            return 'other';
        },
        antiBotStatus: () => {
            if (pageText.includes('pardon the interruption') || document.querySelector('#sec-text-container')) return 'blocked_perimeterx';
            if (pageText.includes('sit tight') || url.includes('queue-it.net')) return 'queue_it';
            return 'clear';
        },
        category: () => {
            if (url.includes('sports')) return 'sports';
            if (url.includes('concerts') || url.includes('music')) return 'concerts';
            if (url.includes('arts-theater') || url.includes('theater')) return 'theater';
            if (url.includes('family')) return 'family';
            return null;
        },
        status: (t) => {
            const s = (t || pageText).toLowerCase();
            if (s.includes('sold out') || s.includes('no tickets match')) return 'sold_out';
            if (s.includes('on sale date and time')) return 'future_sale';
            if (s.includes('presale happens') || s.includes('unlock')) return 'presale';
            if (Enrichment.pageType() === 'queue') return 'queue';
            return 'available';
        },
        isResale: (t) => /verified resale/i.test(t),
        obstructed: (t) => /obstructed|limited view|possible obstruction/i.test(t),
    };

    // ============================================================================
    // 4. SCRAPERS
    // ============================================================================

    const Scraper = {

        pageFilters: () => {
            try {
                // 1. Grab Quantity Dropdown
                const qtySelect = document.querySelector('select[data-bdd="mobileQtyDropdown"], #filter-bar-quantity');
                const selectedQuantity = qtySelect ? parseInt(qtySelect.value) : null;

                // 2. Grab Min Price (Check input box first, fallback to slider ARIA attribute)
                const minInput = document.querySelector('[data-bdd="exposed-mobile-filter-price-slider-min"] input');
                const minSlider = document.querySelector('[aria-label*="Minimum ticket price"]');
                let minPriceText = minInput ? minInput.value : (minSlider ? minSlider.getAttribute('aria-valuenow') : null);
                
                // 3. Grab Max Price
                const maxInput = document.querySelector('[data-bdd="exposed-mobile-filter-price-slider-max"] input');
                const maxSlider = document.querySelector('[aria-label*="Maximum ticket price"]');
                let maxPriceText = maxInput ? maxInput.value : (maxSlider ? maxSlider.getAttribute('aria-valuenow') : null);

                return {
                    filterQuantity: selectedQuantity,
                    filterMinPrice: Parsers.price(minPriceText),
                    filterMaxPrice: Parsers.price(maxPriceText)
                };
            } catch (e) { 
                return {}; 
            }
        },


        ldJson: () => {
            try {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                const found = [];
                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);
                        const graph = data["@graph"] || (Array.isArray(data) ? data : [data]);
                        for (const item of graph) {
                            const types = Array.isArray(item["@type"]) ? item["@type"] : [item["@type"] || ""];
                            if (!types.some(t => t.toLowerCase().includes("event"))) continue;
                            found.push({
                                source: "ld+json",
                                eventName: item.name?.toLowerCase(),
                                eventCategory: types[0],
                                date: item.startDate?.split("T")[0],
                                time: item.startDate?.split("T")[1]?.substring(0, 5),
                                venue: item.location?.name,
                                city: item.location?.address?.addressLocality?.toLowerCase(),
                                price: item.offers?.lowPrice ? parseFloat(item.offers.lowPrice) : null,
                                currency: item.offers?.priceCurrency || "USD",
                                availabilityStatus: item.offers?.availability?.includes("InStock") ? "available" : "sold_out",
                                url: item.url || url
                            });
                        }
                    } catch (e) {}
                }
                return found;
            } catch (e) { return []; }
        },

        ticketListings: () => {
            const collected = [];
            
            // Target the ticket list panel - covering standard lists, Quick Picks, and test IDs
            const rows = document.querySelectorAll(
                'li[data-bdd*="quick-picks-list-item"], ' +
                'li[data-bdd*="list-item-primary"], ' +
                'li[aria-label*="Sec"], ' +
                '[data-testid="offer-card"], ' +
                'div[class*="ticket-card"]'
            );

            rows.forEach(row => {
                try {
                    const rowText = getText(row);
                    if (!rowText) return;

                    // 1. Try to grab the exact price from Quick Pick attributes or specific spans
                    const priceAttr = row.getAttribute('data-price');
                    const priceNode = row.querySelector('[data-bdd="quick-pick-price-button"]');
                    const priceText = priceNode ? getText(priceNode) : null;
                    
                    const extractedPrice = Parsers.price(priceAttr) || Parsers.price(priceText) || Parsers.price(rowText);

                    // Skip rows that don't have a price (like the "Buy Now, Pay Later" PayPal merch slot)
                    if (!extractedPrice) return;

                    // 2. Try to grab exact Section/Row from the Quick Pick description span
                    const descNode = row.querySelector('[data-bdd="quick-pick-item-desc"]');
                    const descText = descNode ? (descNode.getAttribute('aria-label') || getText(descNode)) : rowText;

                    // 3. Check exact Ticket Type branding if available
                    const typeNode = row.querySelector('[data-bdd="branding-ticket-text"]');
                    const typeText = typeNode ? getText(typeNode) : rowText;

                    collected.push({
                        source: "dom_ticket_listing",
                        eventName: getText(document.querySelector('h1'))?.toLowerCase(), 
                        price: extractedPrice,
                        section: extractByPattern(descText, {s: /(?:Sec|Section)\s*([A-Za-z0-9]+)/i}),
                        row: extractByPattern(descText, {r: /Row\s*([A-Za-z0-9]+)/i}),
                        seat: extractByPattern(rowText, {st: /Seat\s*([\d\-,\s]+)/i}),
                        isVIP: /VIP/i.test(rowText),
                        ticketType: /Verified Resale/i.test(typeText) ? 'resale' : 'standard',
                        availabilityStatus: 'available',
                        info: rowText
                    });
                } catch (e) { console.error('Ticket row parse error', e); }
            });
            
            return collected;
        },

        eventCards: () => {
            const collected = [];
            // Target event cards on search/discover pages
            document.querySelectorAll('a[href*="/event/"], [data-testid="event-list-item"]').forEach(card => {
                try {
                    const text = getText(card);
                    if (!text || text.length < 10) return;
                    
                    const href = card.tagName === 'A' ? card.getAttribute('href') : card.querySelector('a')?.getAttribute('href');

                    let eventName = getText(card.querySelector('h3, [data-testid="event-title"]'));
                    if (!eventName && href) {
                         const match = href.match(/\/event\/([a-z0-9]+)/i);
                         if (!match) return; // Skip if it's not a valid event link
                         eventName = text.split('\n')[0]; // Fallback to first line of text
                    }

                    if (eventName) {
                        collected.push({
                            source: "dom_event_card",
                            url: href || url,
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

        checkout: () => {
            if (!url.includes('checkout')) return [];
            const collected = [];
            try {
                // TM checkout has an order summary panel
                const summaryPanel = document.querySelector('[data-testid="order-summary"], [class*="order-summary"]');
                if (summaryPanel) {
                    const text = getText(summaryPanel);
                    const eventName = getText(document.querySelector('h1, [data-testid="event-name"]'));
                    
                    collected.push({
                        source: "checkout_summary",
                        eventName: eventName?.toLowerCase(),
                        price: Parsers.price(text),
                        ticketCount: Parsers.ticketCount(text),
                        date: Parsers.date(text),
                        info: "checkout_page",
                        availabilityStatus: "available"
                    });
                }
            } catch (e) {}
            return collected;
        }
    };

    // ============================================================================
    // 5. MAIN EXECUTION
    // ============================================================================

    try {
        let scraped = [];

        if (url.includes('checkout')) {
            scraped.push(...Scraper.checkout());
        }
        scraped.push(...Scraper.ldJson());
        scraped.push(...Scraper.ticketListings());
        scraped.push(...Scraper.eventCards());

        // Fallback for empty pages (like queues or blocked pages)
        if (scraped.length === 0) {
            scraped.push({
                source: "fallback_metadata",
                url: url,
                eventName: getText(document.querySelector('h1'))?.toLowerCase() || 'unknown',
                info: "No specific elements found. Check antiBot state."
            });
        }

        const filters = Scraper.pageFilters();

        const meta = {
            pageType: Enrichment.pageType(),
            antiBotStatus: Enrichment.antiBotStatus(),
            eventCategory: Enrichment.category(),
            globalStatus: Enrichment.status(pageText),
            ...filters // Inject the scraped filters here
        };

        const seen = new Set();
        
        scraped.forEach(item => {
            const key = `${item.eventName}-${item.date || 'nodate'}-${item.section || 'nosection'}-${item.source}`;
            if (!seen.has(key)) {
                seen.add(key);
                
                // Inherit the global status if the specific item doesn't have a definitive one
                let finalStatus = item.availabilityStatus;
                if (!finalStatus || finalStatus === 'available') {
                    if (meta.globalStatus === 'sold_out' || meta.globalStatus === 'queue' || meta.globalStatus === 'presale') {
                        finalStatus = meta.globalStatus;
                    }
                }

                results.push({
                    ...item,
                    ...meta,
                    availabilityStatus: finalStatus,
                    parsedTime: Parsers.time(item.time || item.date || ''),
                    isResale: Enrichment.isResale(item.info),
                    obstructedView: Enrichment.obstructed(item.info),
                });
            }
        });

    } catch (e) {
        console.error("Ticketmaster Scraper failed", e);
    }

    return results;
})();