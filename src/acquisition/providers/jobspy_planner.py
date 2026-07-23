"""
src/acquisition/providers/jobspy_planner.py
===========================================

Generates JobSpy-specific search queries. Replaces Cartesian product explosion
with prioritized, layered, and budgeted queries. Provider-specific strategies
format the search terms appropriately.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class JobSpyQuery:
    keyword: str
    location: str
    track: str
    provider: str
    search_profile: str
    layer: str


def _quote_if_needed(val: str) -> str:
    val = val.strip()
    if not val:
        return ""
    if " " in val and not (val.startswith('"') and val.endswith('"')):
        return f'"{val}"'
    return val


class ProviderSearchStrategy(ABC):
    @abstractmethod
    def format_query(self, keyword: str, negative_keywords: list[str]) -> str:
        """Format the keyword string for the specific provider."""
        pass


class GoogleStrategy(ProviderSearchStrategy):
    def format_query(self, keyword: str, negative_keywords: list[str]) -> str:
        # Google accepts robust boolean logic.
        quoted = _quote_if_needed(keyword)
        neg_parts = []
        for neg in negative_keywords:
            neg = neg.strip()
            if neg:
                neg_parts.append(f"-{_quote_if_needed(neg)}")
        if neg_parts:
            return f"{quoted} {' '.join(neg_parts)}"
        return quoted


class IndeedStrategy(ProviderSearchStrategy):
    def format_query(self, keyword: str, negative_keywords: list[str]) -> str:
        # Indeed is fairly standard, supports minus sign for exclusion.
        quoted = _quote_if_needed(keyword)
        neg_parts = []
        for neg in negative_keywords:
            neg = neg.strip()
            if neg:
                neg_parts.append(f"-{_quote_if_needed(neg)}")
        if neg_parts:
            return f"{quoted} {' '.join(neg_parts)}"
        return quoted


class LinkedInStrategy(ProviderSearchStrategy):
    def format_query(self, keyword: str, negative_keywords: list[str]) -> str:
        # LinkedIn prefers precise titles and often breaks with complex booleans.
        return _quote_if_needed(keyword)


class JobSpySearchPlanner:
    """
    Search Planner specific to JobSpy.
    Generates budgeted, layered queries (no Cartesian products).
    Applies provider-specific query formatting.
    """

    def __init__(self, profiles_config: dict):
        self.profiles_config = profiles_config
        self.strategies = {
            "google": GoogleStrategy(),
            "indeed": IndeedStrategy(),
            "linkedin": LinkedInStrategy(),
        }

    def generate_planned_searches(self, locations: list[str]) -> list[JobSpyQuery]:
        """
        Generate queries for each provider based on profile budgets and layers.
        """
        all_queries: list[JobSpyQuery] = []

        if not self.profiles_config:
            return all_queries

        # Sort profiles by priority (highest first)
        sorted_profiles = sorted(
            self.profiles_config.items(),
            key=lambda item: item[1].get("priority", 0),
            reverse=True,
        )

        for profile_name, profile_data in sorted_profiles:
            providers = profile_data.get("providers", ["google", "indeed", "linkedin"])
            priority = profile_data.get("priority", 50)

            # Map priority to tracking tier
            if priority >= 100:
                track = "TIER_S"
            elif priority >= 80:
                track = "TIER_A"
            elif priority >= 60:
                track = "TIER_B"
            else:
                track = "TIER_C"

            max_queries = profile_data.get("max_queries", 250)
            max_titles = profile_data.get("max_titles", 15)
            max_frameworks = profile_data.get("max_frameworks", 8)

            layers = profile_data.get("layers", {})
            roles = layers.get("roles", [])[:max_titles]
            frameworks = layers.get("frameworks", [])[:max_frameworks]
            platforms = layers.get("platforms", [])
            negative_keywords = profile_data.get("negative_keywords", [])

            for provider in providers:
                strategy = self.strategies.get(provider, GoogleStrategy())
                provider_query_count = 0

                # Combine layers logically but independently (Layered approach)
                layer_terms = [
                    ("roles", roles),
                    ("frameworks", frameworks),
                    ("platforms", platforms),
                ]

                for layer_name, terms in layer_terms:
                    for term in terms:
                        if provider_query_count >= max_queries:
                            break

                        fmt_keyword = strategy.format_query(term, negative_keywords)
                        for loc in locations:
                            all_queries.append(
                                JobSpyQuery(
                                    keyword=fmt_keyword,
                                    location=loc,
                                    track=track,
                                    provider=provider,
                                    search_profile=profile_name,
                                    layer=layer_name,
                                )
                            )

                        # Count the base term as 1 against the budget
                        provider_query_count += 1

        return all_queries
