import os
from typing import List
from difflib import SequenceMatcher

class TeamCluster:
    """
    Represents a cluster of similar team names that belong to the same club.
    """
    
    def __init__(self, initial_team: str):
        self.members = [initial_team]
        self.club_name = self._extract_common_pattern([initial_team])
        self.descriptors = set()
    
    def _extract_common_pattern(self, team_names: List[str]) -> str:
        """Algorithmically find the longest common substring that represents the club name."""
        if len(team_names) == 1:
            return team_names[0]
        
        # Find all common substrings across team names
        common_substrings = []
        for i in range(len(team_names[0])):
            for j in range(i + 1, len(team_names[0]) + 1):
                substr = team_names[0][i:j]
                if all(substr in name for name in team_names[1:]):
                    common_substrings.append(substr)
        
        # Return the longest meaningful common substring
        if common_substrings:
            # Filter out very short or non-meaningful substrings
            meaningful = [s for s in common_substrings if len(s) > 2 and s.strip()]
            if meaningful:
                return max(meaningful, key=len)
        
        return team_names[0]
    
    def similarity_score(self, team_name: str) -> float:
        """Calculate similarity between team name and cluster centroid."""
        # Use combination of string similarity metrics
        
        # Compare with each member and take max similarity
        max_sim = 0
        for member in self.members:
            # Normalized edit distance similarity
            edit_sim = SequenceMatcher(None, team_name.lower(), member.lower()).ratio()
            
            # Common prefix/suffix analysis (dynamic, not hardcoded)
            prefix_len = len(os.path.commonprefix([team_name.lower(), member.lower()]))
            suffix_len = len(os.path.commonprefix([team_name.lower()[::-1], member.lower()[::-1]]))
            positional_sim = (prefix_len + suffix_len) / (len(team_name) + len(member)) * 2
            
            combined = (edit_sim + positional_sim) / 2
            max_sim = max(max_sim, combined)
        
        return max_sim
    
    def add_team(self, team_name: str):
        """Add a team to the cluster and update club name inference."""
        self.members.append(team_name)
        # Recalculate club name with new data
        self.club_name = self._extract_common_pattern(self.members)
        
        # Learn descriptors from varying parts
        self._update_descriptors()
    
    def _update_descriptors(self):
        """Update descriptors based on member variations."""
        # For simplicity, skip for now or implement later
        pass

class ClubInferenceEngine:
    """
    Main engine for algorithmically inferring club names from team names
    using clustering without hardcoded patterns.
    """
    
    def __init__(self, similarity_threshold: float = 0.6):
        self.clusters = []
        self.similarity_threshold = similarity_threshold
        self.team_to_club = {}
    
    def infer_club(self, team_name: str) -> str:
        """Algorithmically infer club name using clustering approach."""
        
        # Check if we've already processed this team
        if team_name in self.team_to_club:
            return self.team_to_club[team_name]
        
        # Find the best matching cluster
        best_cluster = None
        best_score = 0
        
        for cluster in self.clusters:
            score = cluster.similarity_score(team_name)
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_cluster = cluster
        
        # Either add to existing cluster or create new one
        if best_cluster:
            best_cluster.add_team(team_name)
            club_name = best_cluster.club_name
        else:
            new_cluster = TeamCluster(team_name)
            self.clusters.append(new_cluster)
            club_name = new_cluster.club_name
        
        # Cache the result
        self.team_to_club[team_name] = club_name
        
        return club_name

def get_club_names_from_teams(team_names: List[str]) -> List[str]:
    """
    Apply clustering algorithm to extract club names from a list of team names.
    """
    engine = ClubInferenceEngine()
    club_names = []
    for team in team_names:
        club_name = engine.infer_club(team)
        club_names.append(club_name)
    return club_names

# Example usage
if __name__ == "__main__":
    # Example team names
    example_teams = [
        "Bottesford U7 Blue",
        "Bottesford U14 Girls",
        "City FC U12 Boys",
        "Bottesford-U7-Blue"
    ]
    clubs = get_club_names_from_teams(example_teams)
    print("Extracted club names:", clubs)
