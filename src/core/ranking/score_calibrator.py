from typing import Tuple

class ScoreCalibrator:
    """
    Release 3.1.5 Phase H: Score Calibration Engine.
    Spreads raw scores naturally to prevent clustering and create clear separation:
    - 90-100: Exceptional
    - 80-89: Strong
    - 70-79: Good
    - 60-69: Borderline
    - <60: Reject
    """
    @staticmethod
    def calibrate(raw_score: float) -> Tuple[float, str]:
        # Sigmoid-like stretch for scores around 60-80 to increase variance
        if raw_score >= 85.0:
            calibrated = 90.0 + (raw_score - 85.0) * (10.0 / 15.0)
            bucket = "Exceptional"
        elif raw_score >= 70.0:
            calibrated = 80.0 + (raw_score - 70.0) * (9.0 / 15.0)
            bucket = "Strong"
        elif raw_score >= 55.0:
            calibrated = 70.0 + (raw_score - 55.0) * (9.0 / 15.0)
            bucket = "Good"
        elif raw_score >= 40.0:
            calibrated = 60.0 + (raw_score - 40.0) * (9.0 / 15.0)
            bucket = "Borderline"
        else:
            calibrated = raw_score * (59.0 / 40.0)
            bucket = "Reject"

        return round(max(0.0, min(100.0, calibrated)), 2), bucket
