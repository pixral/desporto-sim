"""Static club list for the mock world. Strength is a rough 0-100 quality rating (mock only).

Club names are used purely as labels; all results, odds and news are simulated.
"""

from app.domain.sports import CompetitionInfo

COMPETITIONS: dict[str, CompetitionInfo] = {
    "BL1": CompetitionInfo(code="BL1", name="Bundesliga", country="Germany", kind="league", color="#d8232a"),
    "PL": CompetitionInfo(code="PL", name="Premier League", country="England", kind="league", color="#6a2c91"),
    "LL": CompetitionInfo(code="LL", name="La Liga", country="Spain", kind="league", color="#f08c00"),
    "SA": CompetitionInfo(code="SA", name="Serie A", country="Italy", kind="league", color="#1f6fd1"),
    "UCL": CompetitionInfo(code="UCL", name="Champions League", country="Europe", kind="cup", color="#24318f"),
}

DOMESTIC_LEAGUES = ("BL1", "PL", "LL", "SA")

# (id, name, short, strength, popular)
CLUBS: dict[str, list[tuple[str, str, str, int, bool]]] = {
    "BL1": [
        ("FCB", "Bayern Munich", "Bayern", 94, True),
        ("B04", "Bayer Leverkusen", "Leverkusen", 85, False),
        ("BVB", "Borussia Dortmund", "Dortmund", 85, True),
        ("RBL", "RB Leipzig", "Leipzig", 83, False),
        ("VFB", "VfB Stuttgart", "Stuttgart", 81, False),
        ("SGE", "Eintracht Frankfurt", "Frankfurt", 81, False),
        ("SCF", "SC Freiburg", "Freiburg", 77, False),
        ("M05", "Mainz 05", "Mainz", 76, False),
        ("WOB", "VfL Wolfsburg", "Wolfsburg", 75, False),
        ("BMG", "Borussia Mönchengladbach", "Gladbach", 75, False),
        ("TSG", "TSG Hoffenheim", "Hoffenheim", 75, False),
        ("SVW", "Werder Bremen", "Bremen", 74, False),
        ("FCU", "Union Berlin", "Union", 73, False),
        ("FCA", "FC Augsburg", "Augsburg", 72, False),
        ("KOE", "1. FC Köln", "Köln", 70, False),
        ("HSV", "Hamburger SV", "Hamburg", 70, False),
        ("STP", "FC St. Pauli", "St. Pauli", 69, False),
        ("FCH", "1. FC Heidenheim", "Heidenheim", 68, False),
    ],
    "PL": [
        ("LIV", "Liverpool", "Liverpool", 91, True),
        ("ARS", "Arsenal", "Arsenal", 91, True),
        ("MCI", "Manchester City", "Man City", 90, True),
        ("CHE", "Chelsea", "Chelsea", 86, True),
        ("NEW", "Newcastle United", "Newcastle", 84, False),
        ("AVL", "Aston Villa", "Villa", 83, False),
        ("TOT", "Tottenham Hotspur", "Spurs", 82, False),
        ("MUN", "Manchester United", "Man United", 81, True),
        ("NFO", "Nottingham Forest", "Forest", 80, False),
        ("BHA", "Brighton & Hove Albion", "Brighton", 80, False),
        ("CRY", "Crystal Palace", "Palace", 79, False),
        ("BOU", "AFC Bournemouth", "Bournemouth", 78, False),
        ("BRE", "Brentford", "Brentford", 77, False),
        ("FUL", "Fulham", "Fulham", 77, False),
        ("EVE", "Everton", "Everton", 76, False),
        ("WHU", "West Ham United", "West Ham", 76, False),
        ("WOL", "Wolverhampton Wanderers", "Wolves", 73, False),
        ("LEE", "Leeds United", "Leeds", 72, False),
        ("SUN", "Sunderland", "Sunderland", 71, False),
        ("BUR", "Burnley", "Burnley", 70, False),
    ],
    "LL": [
        ("RMA", "Real Madrid", "Real Madrid", 91, True),
        ("FCBA", "FC Barcelona", "Barcelona", 91, True),
        ("ATM", "Atlético Madrid", "Atlético", 86, False),
        ("ATH", "Athletic Club", "Athletic", 81, False),
        ("VIL", "Villarreal", "Villarreal", 81, False),
        ("BET", "Real Betis", "Betis", 79, False),
        ("RSO", "Real Sociedad", "Sociedad", 77, False),
        ("CEL", "Celta Vigo", "Celta", 75, False),
        ("SEV", "Sevilla", "Sevilla", 75, False),
        ("OSA", "Osasuna", "Osasuna", 74, False),
        ("GIR", "Girona", "Girona", 74, False),
        ("RAY", "Rayo Vallecano", "Rayo", 74, False),
        ("VAL", "Valencia", "Valencia", 74, False),
        ("MLL", "RCD Mallorca", "Mallorca", 73, False),
        ("GET", "Getafe", "Getafe", 73, False),
        ("ESP", "RCD Espanyol", "Espanyol", 72, False),
        ("ALA", "Deportivo Alavés", "Alavés", 72, False),
        ("ELC", "Elche", "Elche", 70, False),
        ("LEV", "Levante", "Levante", 69, False),
        ("OVI", "Real Oviedo", "Oviedo", 68, False),
    ],
    "SA": [
        ("INT", "Inter", "Inter", 88, True),
        ("NAP", "Napoli", "Napoli", 86, False),
        ("JUV", "Juventus", "Juventus", 84, True),
        ("ATA", "Atalanta", "Atalanta", 84, False),
        ("MIL", "AC Milan", "Milan", 84, True),
        ("ROM", "AS Roma", "Roma", 82, False),
        ("BOL", "Bologna", "Bologna", 80, False),
        ("LAZ", "Lazio", "Lazio", 80, False),
        ("FIO", "Fiorentina", "Fiorentina", 79, False),
        ("COM", "Como", "Como", 77, False),
        ("TOR", "Torino", "Torino", 75, False),
        ("UDI", "Udinese", "Udinese", 74, False),
        ("GEN", "Genoa", "Genoa", 73, False),
        ("CAG", "Cagliari", "Cagliari", 72, False),
        ("SAS", "Sassuolo", "Sassuolo", 72, False),
        ("PAR", "Parma", "Parma", 71, False),
        ("LEC", "Lecce", "Lecce", 70, False),
        ("HVE", "Hellas Verona", "Verona", 70, False),
        ("PIS", "Pisa", "Pisa", 69, False),
        ("CRE", "Cremonese", "Cremonese", 69, False),
    ],
    # Clubs that only appear in the Champions League in this simulation.
    "OTHER": [
        ("PSG", "Paris Saint-Germain", "PSG", 90, True),
        ("SLB", "Benfica", "Benfica", 81, False),
        ("SCP", "Sporting CP", "Sporting", 81, False),
        ("FCP", "FC Porto", "Porto", 80, False),
        ("PSV", "PSV Eindhoven", "PSV", 80, False),
        ("ASM", "AS Monaco", "Monaco", 79, False),
        ("OM", "Olympique de Marseille", "Marseille", 79, False),
        ("AJA", "Ajax", "Ajax", 78, False),
        ("FEY", "Feyenoord", "Feyenoord", 78, False),
        ("GAL", "Galatasaray", "Galatasaray", 78, False),
        ("CLB", "Club Brugge", "Brugge", 77, False),
        ("CEL1", "Celtic", "Celtic", 75, False),
        ("OLY", "Olympiacos", "Olympiacos", 75, False),
    ],
}

COUNTRY = {"BL1": "Germany", "PL": "England", "LL": "Spain", "SA": "Italy", "OTHER": "Europe"}

# Champions League quota taken from each domestic league's top of the table (by strength in year one).
UCL_QUOTA = {"PL": 7, "BL1": 6, "LL": 5, "SA": 5}

# Per-team base goals (per match, before home advantage) for the hidden "true" model.
LEAGUE_BASE_GOALS = {"BL1": 1.52, "PL": 1.40, "LL": 1.28, "SA": 1.32, "UCL": 1.42}
