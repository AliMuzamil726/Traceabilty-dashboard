"""QR Tracing use cases: lots, bales, images, labels, resolving codes, public and internal trace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core import audit
from core.config import Settings
from core.database import utcnow
from core.deps import CurrentOfficer
from core.errors import NotFoundError, ValidationAppError
from module_6 import public_api as heaps
from module_7.models import ACTIVE, TYPE_BALE, TYPE_HEAP, QrToken
from module_7.repository import ScanRepository, TokenRepository
from module_7.services import cache, images, labels, trace
from module_7.services.tokens import TokenService, looks_like_token
from shared.repositories.sites import SiteRepository

MAX_LABELS = 480
_TRACE_URL = re.compile(r"/trace/([A-Za-z2-7]{12})(?:[/?#]|$)")


@dataclass(frozen=True)
class Resolved:
    kind: str  # bale | heap
    heap_id: str
    bale_serial: str | None
    token: str | None
    token_status: str | None


class QrService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.tokens = TokenRepository(session)
        self.scans = ScanRepository(session)

    @property
    def base_url(self) -> str:
        """The address printed on labels: Settings first, then ``.env`` (D-119).

        A localhost address can only be opened on this computer, so when that is all
        there is, this computer's address on the network is used instead (D-123).
        """
        from core import app_settings
        from core.network import reachable_base_url

        configured = str(
            app_settings.setting_or(
                "qr.public_base_url", self.settings.public_base_url, self.session
            )
        )
        return reachable_base_url(configured)

    def url(self, token: str) -> str:
        return images.trace_url(self.base_url, token)

    # ------------------------------------------------------------------ public

    def public_trace(self, token_text: str) -> tuple[dict[str, Any], QrToken] | None:
        """The privacy-filtered payload, or None for unknown or revoked codes (same answer)."""
        token = self.tokens.by_token(token_text) if looks_like_token(token_text) else None
        if token is None or token.status != ACTIVE:
            return None
        key = (str(self.session.get_bind().url), token.token)
        payload = cache.get(key)
        if payload is None:
            bale = None
            if token.token_type == TYPE_BALE:
                bale = heaps.get_bale(self.session, token.bale_serial or "")
                if bale is None or bale.status != "active":
                    return None
            f = trace.facts(self.session, token.heap_id)
            if f is None:
                return None
            payload = trace.public_payload(f, bale)
            cache.put(key, payload)
        return payload, token

    # ------------------------------------------------------------------ lots and bales

    def lots(self, *, crop: str | None, site_id: str | None) -> list[dict[str, Any]]:
        out = []
        for h in heaps.list_heaps(self.session, heaps.HeapQuery(crop=crop, site_id=site_id)):
            token = self.tokens.active_for_heap(h.heap_id)
            out.append(
                {
                    "heap_id": h.heap_id,
                    "crop": h.crop,
                    "status": h.status,
                    "site_id": h.site_id,
                    "opened_at": h.opened_at,
                    "closed_at": h.closed_at,
                    "token": token.token if token else None,
                }
            )
        return out

    def overview(self, heap_id: str) -> dict[str, Any]:
        heap = heaps.get_heap(self.session, heap_id)
        if heap is None:
            raise NotFoundError("That heap does not exist.", code="heap_not_found")
        totals = heaps.get_heap_totals(self.session, heap.heap_id)
        assert totals is not None
        token = self.tokens.active_for_heap(heap.heap_id)
        site = SiteRepository(self.session).get(heap.site_id)
        ids = [t.id for t in self.tokens.for_heap_bales(heap.heap_id)] + (
            [token.id] if token else []
        )
        total, public, last = self.scans.summary(ids)
        lineage = heaps.get_heap_lineage(self.session, heap.heap_id)
        return {
            "heap_id": heap.heap_id,
            "crop": heap.crop,
            "kind": "Heap" if heap.crop == "cotton" else "Batch",
            "status": heap.status,
            "site_name": site.name if site else None,
            "site_address": site.address if site else None,
            "opened_at": heap.opened_at,
            "closed_at": heap.closed_at,
            "input_kg": float(totals.input_kg),
            "outturn_ratio_pct": heap.outturn_ratio_pct,
            "expected_output_kg": float(totals.expected_output_kg),
            "bales_made": totals.bales_made,
            "max_bales": totals.max_bales,
            "token": token.token if token else None,
            "trace_url": self.url(token.token) if token else None,
            "scans_total": total,
            "scans_public": public,
            "last_scan_at": last,
            # The people behind the lot: the officer at the gate needs the names, not
            # just an aggregate, to answer "whose cotton is in this heap?".
            "farmers": [
                {
                    "farmer_id": f.farmer_id,
                    "sawie_id": f.sawie_id,
                    "farmer_name": f.farmer_name,
                    "kg": float(f.kg),
                    "pct": float(f.pct),
                }
                for f in (lineage.farmers if lineage else ())
            ],
            "base_url": self.base_url,
            "base_url_is_local": images.is_local(self.base_url),
        }

    def bales(self, heap_id: str) -> list[dict[str, Any]]:
        heap = heaps.get_heap(self.session, heap_id)
        if heap is None:
            raise NotFoundError("That heap does not exist.", code="heap_not_found")
        tokens = {}
        for t in self.tokens.for_heap_bales(heap.heap_id):
            current = tokens.get(t.bale_serial)
            if (
                current is None
                or t.status == ACTIVE
                or (current.status != ACTIVE and t.created_at > current.created_at)
            ):
                tokens[t.bale_serial] = t
        counts = self.scans.counts_by_token([t.id for t in tokens.values()])
        out = []
        for b in heaps.list_bales(self.session, heap.heap_id, include_voided=True):
            t = tokens.get(b.bale_serial)
            out.append(
                {
                    "bale_serial": b.bale_serial,
                    "weight_kg": b.weight_kg,
                    "bale_status": b.status,
                    "created_at": b.created_at,
                    "token": t.token if t else None,
                    "token_status": t.status if t else None,
                    "trace_url": self.url(t.token) if t else None,
                    "label_print_count": t.label_print_count if t else 0,
                    "last_printed_at": t.last_printed_at if t else None,
                    "scan_count": counts.get(t.id, 0) if t else 0,
                }
            )
        return out

    # ------------------------------------------------------------------ images and labels

    def token_for_image(self, token_text: str) -> QrToken:
        token = self.tokens.by_token(token_text)
        if token is None:
            raise NotFoundError("That code does not exist.", code="qr_token_not_found")
        return token

    def _active_bale_tokens(self, serials: list[str]) -> list[tuple[QrToken, heaps.BaleDTO]]:
        unique = list(dict.fromkeys(s.strip() for s in serials if s.strip()))
        if not unique:
            raise ValidationAppError("Choose at least one bale.", code="qr_no_bales")
        if len(unique) > MAX_LABELS:
            raise ValidationAppError(f"At most {MAX_LABELS} labels at a time.", code="qr_too_many")
        out = []
        for serial in unique:
            bale = heaps.get_bale(self.session, serial)
            token = self.tokens.active_for_bale(serial)
            if bale is None or bale.status != "active" or token is None:
                raise ValidationAppError(
                    f"{serial} has no active code.",
                    code="qr_bale_not_active",
                    details={"bale_serial": serial},
                )
            out.append((token, bale))
        return out

    def _label(self, token: QrToken, bale: heaps.BaleDTO) -> labels.Label:
        heap = heaps.get_heap(self.session, bale.heap_id)
        site = SiteRepository(self.session).get(heap.site_id) if heap else None
        return labels.Label(
            url=self.url(token.token),
            serial=bale.bale_serial,
            heap_id=bale.heap_id,
            site_name=site.name if site else "",
            produced=bale.created_at.date(),
        )

    def _count_print(
        self, pairs: list[tuple[QrToken, heaps.BaleDTO]], officer: CurrentOfficer, kind: str
    ) -> None:
        now = utcnow()
        for token, _bale in pairs:
            token.label_print_count += 1
            token.last_printed_at = now
        audit.record(
            "qr_labels",
            pairs[0][0].heap_id,
            kind,
            officer.id,
            {"bale_serials": [b.bale_serial for _, b in pairs], "count": len(pairs)},
            session=self.session,
        )
        self.session.commit()

    def labels_pdf(self, serials: list[str], officer: CurrentOfficer) -> bytes:
        pairs = self._active_bale_tokens(serials)
        content = labels.pdf([self._label(t, b) for t, b in pairs])
        self._count_print(pairs, officer, "print_labels")
        return content

    def label_png(self, serial: str, officer: CurrentOfficer) -> bytes:
        pairs = self._active_bale_tokens([serial])
        content = labels.label_png(self._label(*pairs[0]))
        self._count_print(pairs, officer, "print_label_png")
        return content

    def images_zip(self, serials: list[str]) -> bytes:
        pairs = self._active_bale_tokens(serials)
        return labels.zip_of_pngs([(b.bale_serial, self.url(t.token)) for t, b in pairs])

    # ------------------------------------------------------------------ resolve and trace

    def resolve(self, q: str) -> Resolved:
        text = (q or "").strip()
        if not text:
            raise ValidationAppError(
                "Enter a code, a bale serial or a trace link.", code="qr_query_empty"
            )
        match = _TRACE_URL.search(text)
        candidate = match.group(1).upper() if match else text.upper()
        if looks_like_token(candidate):
            token = self.tokens.by_token(candidate)
            if token is not None:
                return Resolved(
                    token.token_type, token.heap_id, token.bale_serial, token.token, token.status
                )
        bale = heaps.get_bale(self.session, text.upper())
        if bale is not None:
            t = self.tokens.active_for_bale(bale.bale_serial) or self.tokens.latest_for_bale(
                bale.bale_serial
            )
            return Resolved(
                TYPE_BALE,
                bale.heap_id,
                bale.bale_serial,
                t.token if t else None,
                t.status if t else None,
            )
        heap = heaps.get_heap(self.session, text.upper())
        if heap is not None:
            t = self.tokens.active_for_heap(heap.heap_id)
            return Resolved(
                TYPE_HEAP, heap.heap_id, None, t.token if t else None, t.status if t else None
            )
        raise NotFoundError("No bale, lot or code matches that.", code="qr_not_found")

    def internal_bale(self, serial: str, officer: CurrentOfficer) -> dict[str, Any]:
        bale = heaps.get_bale(self.session, serial)
        if bale is None:
            raise NotFoundError("That bale does not exist.", code="bale_not_found")
        f = trace.facts(self.session, bale.heap_id, with_geometry=True)
        assert f is not None
        out = trace.internal_trace(self.session, f, bale, officer_id=officer.id)
        token = self.tokens.active_for_bale(serial)
        out["token"] = token.token if token else None
        return out

    def internal_heap(self, heap_id: str, officer: CurrentOfficer) -> dict[str, Any]:
        f = trace.facts(self.session, heap_id, with_geometry=True)
        if f is None:
            raise NotFoundError("That heap does not exist.", code="heap_not_found")
        out = trace.internal_trace(self.session, f, None, officer_id=officer.id)
        token = self.tokens.active_for_heap(f.heap.heap_id)
        out["token"] = token.token if token else None
        return out

    def scan_summary(self, heap_id: str | None = None) -> dict[str, Any]:
        ids = None
        if heap_id:
            ids = [t.id for t in self.tokens.for_heap_bales(heap_id)]
            heap_token = self.tokens.active_for_heap(heap_id)
            if heap_token:
                ids.append(heap_token.id)
        total, public, last = self.scans.summary(ids)
        return {
            "total": total,
            "public": public,
            "internal": total - public,
            "last_scan_at": last,
            "active_tokens": self.tokens.count_active(heap_ids=[heap_id] if heap_id else None),
            "generated_at": datetime.now(UTC),
        }

    def regenerate(self, serial: str, officer: CurrentOfficer, reason: str | None) -> QrToken:
        bale = heaps.get_bale(self.session, serial)
        if bale is None:
            raise NotFoundError("That bale does not exist.", code="bale_not_found")
        return TokenService(self.session).regenerate(
            serial, officer, reason, bale_active=bale.status == "active", heap_id=bale.heap_id
        )


def clear_cache() -> None:
    cache.invalidate()


__all__ = ["TYPE_HEAP", "QrService", "Resolved"]
