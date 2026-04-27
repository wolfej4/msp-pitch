"""Default MSP service catalog seeded on first run.
Edit/delete these freely from the UI — they're a starting point, not a mandate.
Pricing is illustrative; adjust to your market (Crestview FL / NW Florida SMB)."""

DEFAULT_CATEGORIES = [
    "Foundation",
    "Cybersecurity",
    "Identity & Access",
    "Cloud & Productivity",
    "Backup & DR",
    "Data Protection",
    "Network",
    "Mobile Device Management",
    "Monitoring & Observability",
    "Communications",
    "Print & Document Management",
    "Hardware as a Service",
    "Procurement",
    "Project Services",
    "Strategic",
    "Compliance & Risk",
    "Training & Awareness",
    "Industry: Hospitality",
    "Industry: Healthcare",
    "Industry: Legal",
    "Industry: Financial Services",
    "Industry: Nonprofit",
    "Industry: Manufacturing",
    "General",
]

DEFAULT_SERVICES = [
    # ---- Foundation / Managed IT ----
    {
        "name": "Managed IT - Essentials",
        "category": "Foundation",
        "description": "Per-user help desk, RMM, patch management, asset tracking, and monthly reporting. Business-hours coverage.",
        "default_price": 95.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "Managed IT - Advanced",
        "category": "Foundation",
        "description": "Everything in Essentials plus 24/7 monitoring, after-hours support, and quarterly business reviews (QBRs).",
        "default_price": 145.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "Endpoint RMM & Patch Management",
        "category": "Foundation",
        "description": "Remote monitoring, automated OS/third-party patching, and remote support tooling per device.",
        "default_price": 18.0,
        "price_unit": "per_device",
        "billing_cycle": "monthly",
    },

    # ---- Cybersecurity ----
    {
        "name": "Managed EDR / Antivirus",
        "category": "Cybersecurity",
        "description": "Next-gen endpoint detection & response with centralized alerting and threat remediation.",
        "default_price": 12.0,
        "price_unit": "per_endpoint",
        "billing_cycle": "monthly",
    },
    {
        "name": "DNS & Web Filtering",
        "category": "Cybersecurity",
        "description": "Block malicious domains, phishing, and policy-violating sites at the DNS layer (on and off network).",
        "default_price": 4.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "Email Security & Anti-Phishing",
        "category": "Cybersecurity",
        "description": "Inbound/outbound mail filtering, link rewriting, attachment sandboxing, and impersonation protection.",
        "default_price": 5.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "Security Awareness Training",
        "category": "Cybersecurity",
        "description": "Monthly micro-training and simulated phishing campaigns with reporting.",
        "default_price": 4.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "MFA Rollout & Enforcement",
        "category": "Cybersecurity",
        "description": "Deploy and enforce multi-factor authentication across critical systems (email, VPN, line-of-business apps).",
        "default_price": 750.0,
        "price_unit": "flat",
        "billing_cycle": "one_time",
    },
    {
        "name": "Vulnerability Scanning",
        "category": "Cybersecurity",
        "description": "Recurring internal/external vulnerability scans with prioritized remediation guidance.",
        "default_price": 250.0,
        "price_unit": "flat",
        "billing_cycle": "monthly",
    },

    # ---- Cloud & Productivity ----
    {
        "name": "Microsoft 365 Management",
        "category": "Cloud & Productivity",
        "description": "License management, identity & access, mailbox/SharePoint admin, security baselines.",
        "default_price": 8.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "Microsoft 365 Backup",
        "category": "Cloud & Productivity",
        "description": "3rd-party backup of Exchange, OneDrive, SharePoint, and Teams data with point-in-time recovery.",
        "default_price": 4.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },
    {
        "name": "Google Workspace Management",
        "category": "Cloud & Productivity",
        "description": "Tenant administration, security policy, group/shared drive management, and user lifecycle.",
        "default_price": 8.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },

    # ---- Backup & Recovery ----
    {
        "name": "Server / Workstation Image Backup",
        "category": "Backup & DR",
        "description": "Local + offsite encrypted image backups with verified restore tests.",
        "default_price": 75.0,
        "price_unit": "per_device",
        "billing_cycle": "monthly",
    },
    {
        "name": "Disaster Recovery Plan",
        "category": "Backup & DR",
        "description": "Documented DR plan, tabletop exercise, and RTO/RPO targets for your critical systems.",
        "default_price": 1500.0,
        "price_unit": "flat",
        "billing_cycle": "one_time",
    },

    # ---- Network ----
    {
        "name": "Managed Firewall",
        "category": "Network",
        "description": "Firewall provisioning, security subscriptions, monitoring, and rule changes.",
        "default_price": 95.0,
        "price_unit": "flat",
        "billing_cycle": "monthly",
    },
    {
        "name": "Managed Wi-Fi & Network",
        "category": "Network",
        "description": "Switches and APs monitored 24/7; VLAN/QoS tuning, firmware management, and capacity planning.",
        "default_price": 25.0,
        "price_unit": "per_device",
        "billing_cycle": "monthly",
    },
    {
        "name": "VPN / Remote Access Setup",
        "category": "Network",
        "description": "Site-to-site or client VPN deployment (e.g., WireGuard / IPsec / ZTNA).",
        "default_price": 850.0,
        "price_unit": "flat",
        "billing_cycle": "one_time",
    },

    # ---- VoIP / Communications ----
    {
        "name": "Hosted VoIP / Cloud Phone",
        "category": "Communications",
        "description": "Cloud PBX with desk/soft phones, auto-attendants, voicemail-to-email, and number porting.",
        "default_price": 22.0,
        "price_unit": "per_user",
        "billing_cycle": "monthly",
    },

    # ---- Strategic / Project ----
    {
        "name": "vCIO / Strategic IT Advisory",
        "category": "Strategic",
        "description": "Quarterly IT roadmap, budget planning, vendor management, and executive-level reporting.",
        "default_price": 500.0,
        "price_unit": "flat",
        "billing_cycle": "monthly",
    },
    {
        "name": "Compliance Readiness (HIPAA / PCI / CMMC)",
        "category": "Strategic",
        "description": "Gap assessment, policy authoring, control implementation, and audit prep.",
        "default_price": 3500.0,
        "price_unit": "flat",
        "billing_cycle": "one_time",
    },
    {
        "name": "Onboarding & IT Audit",
        "category": "Strategic",
        "description": "Discovery, documentation of current environment, and remediation roadmap. Required before managed services begin.",
        "default_price": 1250.0,
        "price_unit": "flat",
        "billing_cycle": "one_time",
    },
    {
        "name": "Hardware Procurement (Markup)",
        "category": "Procurement",
        "description": "Workstation, server, and networking hardware sourcing with managed deployment.",
        "default_price": 0.0,
        "price_unit": "flat",
        "billing_cycle": "one_time",
    },

    # ---- Industry-specific (restaurant — leveraging your background) ----
    {
        "name": "Restaurant POS Support Add-On",
        "category": "Industry: Hospitality",
        "description": "POS terminal hardening, network segmentation for payment systems, and after-hours rapid response for service-critical outages.",
        "default_price": 35.0,
        "price_unit": "per_device",
        "billing_cycle": "monthly",
    },
]
