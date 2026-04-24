Strategist Impact Dashboard — Redesigned

  The dashboard has been completely rebuilt from the original 2-page layout
  (with many broken widget references) into a 5-page impact cockpit:

  Pages

  1. Executive Summary — 6 KPI counters (Total Accounts: 38, Focus: 1, One-off:
  9, Territories: 5, AE Partners: 10, Total Engagements: 52) + 4 charts
  (timeline, format mix, territory coverage, territory revenue)
  2. Focus Engagements — Account detail table, quarterly revenue pivot (Aumovio
  growing from $528 to $68K+), revenue trend line chart, QoQ growth rate chart
  3. One-off Engagements — Format breakdown bar chart, timeline by FY, detailed
  engagement table (9 engagements across Advisory, Keynote, Point of View)
  4. Impact Analysis — YoY growth benchmark (advisor portfolio vs Central
  region), revenue by engagement type, all-account quarterly revenue trajectory,
   account-level YoY growth table
  5. Global Filters — Strategist email, FY, engagement type (x2),
  engagement status, territory region, territory area

  Key metrics visible

  - Focus portfolio showing ~1,000% YoY growth in FY2026
  - Portfolio spans 5 territories with 10 AE partners
  - Clear differentiation between Focus (deep, multi-quarter) and One-off
  (targeted) engagements

  What's next (potential improvements)

  - Classify the 42 "Unclassified/tbc" engagements into Focus or One-off in the
  source data
  - Add more Focus accounts as the engagement data grows
  - Normalize quarter naming (FY25-Q1 vs FY25Q1 inconsistency in source data)
  - Add the region benchmark comparison as a dual-axis or side-by-side chart

  The build script is saved at strategist-cockpit/scripts/build_dashboard.py.


A few highlights from the research that could inform future dashboard iterations:

  - Wiseman's 4-domain model maps well to the data you have: Account Outcomes
  (revenue growth), Engagement Quality (Focus vs One-off depth), Strategic
  Influence (territory coverage, AE partnerships), Knowledge Multiplication (not
   yet tracked)
  - Before/After comparison is the gold standard for attribution — the Focus
  Account Revenue Trend chart on the dashboard does exactly this for Aumovio
  - The framework is designed to scale — since the dashboard uses
  strategist_email as a filter, other strategists could use the same dashboard
  by adding their engagement data to the source table