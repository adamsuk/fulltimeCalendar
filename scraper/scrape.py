# scraper/scrape.py - updated with club clustering functions

import some_modules

# Existing code...

def find_common_prefix(strings):
    """Find the longest common prefix among a list of strings."""
    if not strings:
        return ""
    strings = sorted(strings)
    first, last = strings[0], strings[-1]
    i = 0
    min_len = min(len(first), len(last))
    while i < min_len and first[i] == last[i]:
        i += 1
    prefix = first[:i]
    # Adjust to word boundary
    if i < len(first) and first[i] != ' ':
        last_space = prefix.rfind(' ')
        if last_space != -1:
            prefix = prefix[:last_space]
    return prefix.strip()

def cluster_teams_by_club(team_names, similarity_threshold=0.6):
    """
    Cluster team names into clubs.
    """
    clubs = {}
    for team in team_names:
        found = False
        for club in list(clubs.keys()):
            if team.startswith(club) and (len(team) == len(club) or team[len(club)] in [' ', '-']):
                clubs[club].append(team)
                found = True
                break
        if not found:
            words = team.split()
            if len(words) > 1 and words[-1] in ['Blue', 'Red', 'Girls', 'Boys'] and words[-2][0] == 'U':
                club_name = ' '.join(words[:-2])
            elif len(words) > 1 and words[-2][0] == 'U':
                club_name = ' '.join(words[:-2])
            else:
                club_name = team
            clubs.setdefault(club_name, []).append(team)
    return clubs

def infer_clubs_from_teams(team_names):
    clusters = cluster_teams_by_club(team_names)
    result = {}
    for club, teams in clusters.items():
        result[club] = {
            'name': club,
            'teams': teams,
            'team_count': len(teams)
        }
    return result

# More existing code...