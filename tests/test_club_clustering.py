import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scraper.scrape import find_common_prefix, cluster_teams_by_club, infer_clubs_from_teams

def test_find_common_prefix():
    assert find_common_prefix(["Bottesford U7", "Bottesford U14"]) == "Bottesford"
    assert find_common_prefix(["ABC Team", "ABC Club"]) == "ABC"
    assert find_common_prefix(["Hello World", "Hello There"]) == "Hello"
    assert find_common_prefix(["Same", "Same"]) == "Same"
    assert find_common_prefix(["A", "B"]) == ""
    assert find_common_prefix([]) == ""

def test_cluster_teams_by_club():
    teams = ["Bottesford U7 Blue", "Bottesford U14 Girls", "Bottesford Town U10", "Other Club Senior"]
    clusters = cluster_teams_by_club(teams)
    assert any("Bottesford" in club for club in clusters.keys())
    for club, team_list in clusters.items():
        if "Bottesford" in club:
            assert len(team_list) >= 2

def test_infer_clubs_from_teams():
    teams = ["Bottesford U7 Blue", "Bottesford U14 Girls", "Other Club Senior", "Other Club Junior"]
    result = infer_clubs_from_teams(teams)
    assert len(result) >= 2
    for club, info in result.items():
        assert 'name' in info
        assert 'teams' in info
        assert 'team_count' in info

if __name__ == '__main__':
    test_find_common_prefix()
    print("find_common_prefix tests passed")
    test_cluster_teams_by_club()
    print("cluster_teams_by_club tests passed")
    test_infer_clubs_from_teams()
    print("infer_clubs_from_teams tests passed")
    print("All tests passed")