def infer_club_from_team(team_name):
    import re
    pattern = r'\bU\d+\b'
    match = re.search(pattern, team_name)
    if match:
        club_name = team_name[:match.start()].strip()
        if club_name:
            return club_name
    return team_name.split()[0] if team_name.split() else team_name

# Existing code below, assuming it's there
# ...