"""Line-icon set for the bias atlas.

Each value is the inner markup of a 24x24 <svg>, stroked with currentColor.
Drawn to stay legible at 16-18px, which is the range the atlas uses.
"""

ICONS = {
# ---- perception and mindset -------------------------------------------------
"confirmation":   '<circle cx="12" cy="12" r="8.5"/><path d="M8 12.2l2.8 2.8L16.2 9"/>',
"belief-perseverance": '<rect x="5" y="10.5" width="14" height="9.5" rx="1.5"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/><circle cx="12" cy="15" r="1.2"/>',
"mirror-imaging": '<path d="M12 3v18"/><path d="M9 8l-4 4 4 4"/><path d="M15 8l4 4-4 4"/>',
"selective-perception": '<path d="M3.5 12s3.4-4.6 8.5-4.6 8.5 4.6 8.5 4.6-3.4 4.6-8.5 4.6S3.5 12 3.5 12Z"/><circle cx="12" cy="12" r="2"/><path d="M4.5 5.5v13M19.5 5.5v13"/>',

# ---- evidence evaluation ----------------------------------------------------
"vividness":      '<path d="M12 3l2 5.5 5.5 2-5.5 2L12 18l-2-5.5L4.5 10.5 10 8.5Z"/>',
"anchoring":      '<circle cx="12" cy="4.6" r="1.8"/><path d="M12 6.4v13"/><path d="M5.5 12.5a6.5 6.5 0 0 0 13 0"/><path d="M3.5 12.5h3M17.5 12.5h3"/>',
"availability": '<path d="M7 16.5h10a3.5 3.5 0 0 0 .3-7 5 5 0 0 0-9.6-1.4A3.5 3.5 0 0 0 7 16.5Z"/><circle cx="12" cy="12" r="1.4"/><circle cx="6" cy="19" r="1"/><circle cx="9" cy="20.5" r=".7"/>',
"representativeness": '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="2.5 2.5"/><circle cx="12" cy="10" r="2.2"/><path d="M8.5 16.5a3.5 3.5 0 0 1 7 0"/>',
"absence-of-evidence":
                  '<circle cx="10.5" cy="10.5" r="5.5"/><path d="M14.5 14.5L20 20"/><path d="M8.6 10.5h.01M10.5 8.6h.01M12.4 10.5h.01M10.5 12.4h.01"/>',

# ---- estimation and confidence ---------------------------------------------
"overconfidence": '<circle cx="10.5" cy="13.5" r="5.5"/><circle cx="10.5" cy="13.5" r="1.8"/><path d="M14.2 9.8L21 3"/><path d="M18 3h3v3"/>',
"hindsight":      '<circle cx="12.5" cy="12.5" r="7.5"/><path d="M12.5 8.5v4.2l3 1.8"/><path d="M4 8.5V4.5h4"/>',
"base-rate-neglect": '<circle cx="6" cy="6" r="1.2"/><circle cx="12" cy="6" r="1.2"/><circle cx="18" cy="6" r="1.2"/><circle cx="6" cy="12" r="1.2"/><circle cx="18" cy="12" r="1.2"/><circle cx="6" cy="18" r="1.2"/><circle cx="12" cy="18" r="1.2"/><circle cx="18" cy="18" r="1.2"/><circle cx="12" cy="12" r="2.6"/>',
"insensitivity-to-sample-size":
                  '<rect x="5" y="5" width="14" height="14" rx="2"/><circle cx="12" cy="12" r="1.5"/>',

# ---- social and group -------------------------------------------------------
"groupthink": '<circle cx="12" cy="7" r="2.2"/><circle cx="7" cy="16.5" r="2.2"/><circle cx="17" cy="16.5" r="2.2"/><path d="M10.4 8.8L8.4 14.6M13.6 8.8l2 5.8M9.2 16.5h5.6"/>',
"conformity": '<path d="M4 7h6M4 12h6M4 17h6"/><path d="M13 7v6a3 3 0 0 0 3 3h4"/><path d="M17 13l3 3-3 3"/>',
"fundamental-attribution":
                  '<circle cx="9" cy="8" r="3"/><path d="M4 19a5 5 0 0 1 10 0"/><path d="M15.5 6h5v4h-5z"/>',
"loss-aversion":  '<path d="M12 4.5v15.5"/><path d="M5 8h14"/><path d="M6.5 8L4.5 13.5h4z"/><path d="M17.5 8l3 6.5h-6z"/>',

# ---- decision and commitment ------------------------------------------------
"escalation-of-commitment":
                  '<path d="M4 7h5v4.5h5V16h6"/><circle cx="20" cy="19.5" r="1.4"/>',
"framing":        '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M9 5v14"/><path d="M4 11.5h16"/>',
"status-quo": '<path d="M9 5.5v11M15 5.5v11"/><path d="M5 20h14"/>',
"recency":        '<path d="M4 12h16"/><circle cx="19.5" cy="12" r="2"/><circle cx="5" cy="12" r="1"/><circle cx="11.5" cy="12" r="1"/>',

# ---- structural -------------------------------------------------------------
"single-source": '<circle cx="4.5" cy="12" r="2"/><circle cx="19.5" cy="6" r="1.8"/><circle cx="19.5" cy="12" r="1.8"/><circle cx="19.5" cy="18" r="1.8"/><path d="M6.5 12l11-5.2M6.5 12h11M6.5 12l11 5.2"/>',
"inherited-partner-reporting":
                  '<rect x="5" y="5" width="9" height="12" rx="1"/><path d="M14 11h6"/><path d="M17 8l3 3-3 3"/>',
"thin-analytic-coverage": '<circle cx="12" cy="12" r="8" stroke-dasharray="2.5 2.5"/><circle cx="12" cy="12" r="2.4"/>',
"carried-forward-assessment": '<rect x="4" y="6" width="16" height="14" rx="1.5"/><path d="M4 10.5h16M8.5 4v4M15.5 4v4"/><path d="M9.5 15.5h5"/>',
"volume-mistaken-for-development":
                  '<path d="M4 20h16"/><path d="M6.5 20v-3.5"/><path d="M10.5 20v-6.5"/><path d="M14.5 20v-9.5"/><path d="M18.5 20v-12.5"/>',
}

# page slug -> icon key (slug mirrors the wiki filename)
SLUG_ICON = {
    "confirmation-bias": "confirmation",
    "belief-perseverance": "belief-perseverance",
    "mirror-imaging": "mirror-imaging",
    "selective-perception": "selective-perception",
    "vividness-bias": "vividness",
    "anchoring-bias": "anchoring",
    "availability-heuristic": "availability",
    "representativeness-heuristic": "representativeness",
    "absence-of-evidence-fallacy": "absence-of-evidence",
    "overconfidence-bias": "overconfidence",
    "hindsight-bias": "hindsight",
    "base-rate-neglect": "base-rate-neglect",
    "insensitivity-to-sample-size": "insensitivity-to-sample-size",
    "groupthink": "groupthink",
    "conformity-bias": "conformity",
    "fundamental-attribution-error": "fundamental-attribution",
    "loss-aversion": "loss-aversion",
    "escalation-of-commitment": "escalation-of-commitment",
    "framing-effect": "framing",
    "status-quo-bias": "status-quo",
    "recency-bias": "recency",
    "single-source-dependency": "single-source",
    "inherited-partner-reporting": "inherited-partner-reporting",
    "thin-analytic-coverage": "thin-analytic-coverage",
    "carried-forward-assessment": "carried-forward-assessment",
    "volume-mistaken-for-development": "volume-mistaken-for-development",
}


def svg(key, cls="bias-icon"):
    inner = ICONS.get(key)
    if not inner:
        return ""
    return (f'<span class="{cls}" aria-hidden="true"><svg viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg></span>')
