from typing import Dict

class ScoringEngine:
    """
    Final Score (0–100) =
      70% Hard Filters (Pass/Fail -> mapped to base score) 
      + 20% AI Risk Score
      + 10% Social Momentum
      
    Wait, prompt says: "Final score determines alert." 
    And "AI weight must never exceed 30%."
    """
    
    @staticmethod
    def calculate_score(
        hard_filter_passed: bool,
        ai_score: float, # 0-100 (where 100 is High Risk? No, typically Score is Quality. )
                         # Prompt: "AI Risk Score: 0-30 Low Risk". 
                         # So Low Risk is GOOD. 
                         # But Final Score: "Sent if > threshold". High Score = GOOD.
                         # We need to invert AI Risk. 
                         # AI Risk 0 (Good) -> Contribution High. 
                         # Let's Normalize: AI_Contribution = (100 - AI_Risk)
        social_score: float # 0-100 normalized
    ) -> float:
        
        if not hard_filter_passed:
            return 0.0

        # Base score from passing hard filters? 
        # Actually prompt implies Hard Filters are pre-reqs. 
        # The variables passed to score might be subtler on-chain metrics.
        # But let's follow the formula:
        # "Final Score = 70% Hard Filters + ..." 
        # This implies Hard Filters passing gives a base 70 points?
        
        base_score = 70.0
        
        # AI Part (Max 20 pts)
        # AI Risk Score is 0 (Good) to 100 (Bad).
        # We want AI Score contribution to be high if Risk is low.
        # AI_Qual = 100 - ai_risk_score
        # Weighted: AI_Qual * 0.2
        ai_contribution = (100 - ai_score) * 0.20
        
        # Social Part (Max 10 pts)
        # Social score input 0-100
        social_contribution = social_score * 0.10
        
        final = base_score + ai_contribution + social_contribution
        
        # Cap at 100
        return min(100.0, final)
