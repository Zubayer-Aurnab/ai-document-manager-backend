"""Singleton organization settings."""
from typing import Any, Optional

from models.company_settings import CompanySettings
from models.user import User, UserRole
from repositories.company_settings_repository import CompanySettingsRepository


class CompanySettingsService:
    def __init__(self, repo: CompanySettingsRepository | None = None):
        self._repo = repo or CompanySettingsRepository()

    def get(self, _actor: User) -> CompanySettings:
        return self._repo.get_or_create_empty()

    def update(self, actor: User, data: dict[str, Any]) -> tuple[Optional[CompanySettings], Optional[str]]:
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden"
        row = self._repo.get_or_create_empty()
        string_fields = (
            "company_name",
            "legal_name",
            "tagline",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state_region",
            "postal_code",
            "country",
            "website",
        )
        for key in string_fields:
            if key in data:
                val = data[key]
                setattr(row, key, (val.strip() if isinstance(val, str) else val) or None)
        self._repo.save(row)
        return row, None
