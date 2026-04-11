"""
Schémas de données pour le projet Chefs Recommandations.
Utilisés pour la validation des données collectées par les agents.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SocialHandles:
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    tiktok: Optional[str] = None
    twitter: Optional[str] = None


@dataclass
class Chef:
    name: str
    known_for: str
    country: str
    style: str
    social_handles: SocialHandles = field(default_factory=SocialHandles)
    media_presence: list[str] = field(default_factory=list)
    likely_recommends: bool = True


@dataclass
class RecommendationSource:
    chef_name: str
    chef_restaurant: Optional[str] = None
    quote: Optional[str] = None
    source: str = ""
    source_url: Optional[str] = None
    date: Optional[str] = None
    platform: str = "presse"  # presse, social, podcast, interview


@dataclass
class Coordinates:
    lat: float
    lng: float


@dataclass
class Restaurant:
    id: str
    name: str
    address: str
    city: str
    country: str
    coordinates: Optional[Coordinates] = None
    cuisine_type: str = ""
    price_range: str = "€€"  # €, €€, €€€, €€€€
    vibe: str = ""  # bistrot, gastronomique, casual, street food
    tags: list[str] = field(default_factory=list)
    recommendations: list[RecommendationSource] = field(default_factory=list)
    recommendation_count: int = 0
    confidence_score: int = 0
    last_updated: str = ""
