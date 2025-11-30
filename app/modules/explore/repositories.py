import re
from datetime import datetime, timedelta

import unidecode
from sqlalchemy import and_, or_

from app.modules.dataset.models import Author, DataSet, DSMetaData, PublicationType
from core.repositories.BaseRepository import BaseRepository


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def _parse_date(self, s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None

    def _tokens(self, text: str):
        if not text:
            return []
        t = unidecode.unidecode(text).lower().strip()
        t = re.sub(r'[,.":\'()\[\]^;!¡¿?]', "", t)
        return [w for w in t.split() if w]

    # Main filter method
    def filter(
        self, query="", sorting="newest", publication_type="any", tags=None, start_date=None, end_date=None, **kwargs
    ):

        q = self.model.query.join(DataSet.ds_meta_data).outerjoin(DSMetaData.authors).distinct()

        words = self._tokens(query)
        has_query = bool(words)
        has_pub_type = bool(publication_type and publication_type != "any")
        has_tags = any(t.strip() for t in tags)

        sd = self._parse_date(start_date)
        ed = self._parse_date(end_date)

        # No filters
        if not (has_query or has_pub_type or has_tags or sd or ed):
            return q.order_by(DataSet.created_at.desc(), DSMetaData.title.asc()).all()

        # Dates
        if sd:
            q = q.filter(DataSet.created_at >= sd)
        if ed:
            q = q.filter(DataSet.created_at < (ed + timedelta(days=1)))  # día completo

        # Publication type
        if has_pub_type:
            member = next((m for m in PublicationType if m.value.lower() == publication_type.lower()), None)
            if member is not None:
                q = q.filter(DSMetaData.publication_type == member)

        # Tags
        if has_tags:
            clauses = [DSMetaData.tags.ilike(f"%{t.strip()}%") for t in tags if t.strip()]
            if clauses:
                q = q.filter(and_(*clauses))

        # General search
        if has_query:
            per_word_groups = []
            for w in words:
                like = f"%{w}%"
                per_word_groups.append(
                    or_(
                        DSMetaData.title.ilike(like),
                        DSMetaData.description.ilike(like),
                        Author.name.ilike(like),
                        Author.affiliation.ilike(like),
                    )
                )
            q = q.filter(and_(*per_word_groups))

        # Ordering
        if sorting == "oldest":
            q = q.order_by(DataSet.created_at.asc(), DSMetaData.title.asc())
        else:
            q = q.order_by(DataSet.created_at.desc(), DSMetaData.title.asc())

        return q.all()
