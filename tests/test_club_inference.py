import unittest
from scraper.scraper import infer_club_from_team

class TestClubInference(unittest.TestCase):
    def test_happy_path(self):
        self.assertEqual(infer_club_from_team("Bottesford U7 Blue"), "Bottesford")
        self.assertEqual(infer_club_from_team("Bottesford U14 Girls"), "Bottesford")
        self.assertEqual(infer_club_from_team("ClubName U10 Red"), "ClubName")
    
    def test_edge_cases(self):
        self.assertEqual(infer_club_from_team("U7 Blue"), "U7")
        self.assertEqual(infer_club_from_team("Team Only"), "Team")
        self.assertEqual(infer_club_from_team(""), "")

if __name__ == '__main__':
    unittest.main()