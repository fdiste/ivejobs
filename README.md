# Michigan Title IV-E Eligible Job Postings

A simple website listing open MDHHS and private agency jobs that match the
[Michigan Title IV-E Child Welfare Fellowship eligible positions list](https://michildwelfare.org/employment/).

Each posting shows: job title (linked to the posting), employer, county, city, posted date,
closing date, whether it is continuous, and which eligible position it matches.

## Updating the site

Double-click **`update.bat`** (or run `py -m ivejobs.build`). A Chrome window opens briefly off-screen to
read michildwelfare.org, which blocks simple scrapers. When it finishes, open **`docs/index.html`**.

Each update:

1. Reads the eligible positions list from michildwelfare.org/employment. If the site can't be reached, the
   last saved copy (`data/eligible_positions.json`) is used, and you'll see a warning.
2. Downloads every MDHHS posting from the State of Michigan's job feed (governmentjobs.com).
3. Downloads postings from each private agency in `config/agencies.json`.
4. Keeps only postings that match an eligible position (rules in `config/match_rules.json`).
5. Works out the county from the posting title or city (city lookups are cached in `data/city_county.json`).
6. Writes `docs/index.html` (the site), `docs/jobs.csv`, and `docs/jobs.json`.

Setup on a new computer: install Python 3 and Google Chrome, then run `py -m pip install -r requirements.txt`.

## What's covered

- **MDHHS:** all county and central-office postings, filtered by civil-service classification and description
  (for example Services Specialist CPS/Foster Care, Centralized Intake, and Services Specialist Assistant on
  Family Team Support). Adult Services, Assistance Payments, and hospital jobs are excluded.
- **Private agencies:** about 30 Michigan child-placing agencies whose job boards can be read automatically.
  Some agencies have no readable job board (they post only on Indeed, or have no careers page). They're listed
  under "Employers checked" on the site with a link to check directly.
- **Tribal agencies** are not included. Their eligible positions are shown in the reference list.

## Data limitations

- Private agency boards often don't publish a closing date or say whether a posting is continuous. These show
  as "Not listed" or "Not stated". Some boards (UKG Ready, Paycor, Paycom, plain web pages) don't give a
  posted date either.
- Matching is automatic and based on titles and descriptions. Always verify a position with your university's
  Title IV-E Program Coordinator before accepting.

## Maintaining it

- **An agency changed job systems, or shows "Couldn't read this update":** fix its entry in
  `config/agencies.json`. Test it with `py tools/check_agency.py "Agency Name"`, which lists every posting and
  whether it matched.
- **Add an agency:** add an entry to `config/agencies.json`. Supported systems: Paylocity, UKG Pro (UltiPro),
  UKG Ready, ClearCompany, Paycom, Paycor, iCIMS, Workday, AppOne/Paychex, ApplicantPro, and plain HTML pages.
  Use `"ats": "manual"` to only list the careers link.
- **A wrong job appears, or a right one is missing:** adjust the patterns in `config/match_rules.json`.
- **The Fellowship adds a new eligible position:** the update will warn you and fall back to a simple rule built
  from the title. Add a proper rule to `config/match_rules.json`.
