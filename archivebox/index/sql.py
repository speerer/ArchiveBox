__package__ = 'archivebox.index'

from io import StringIO
from pathlib import Path
from typing import List, Tuple, Iterator
from django.db.models import QuerySet
from django.db import transaction

from .schema import Link
from ..util import enforce_types, parse_date
from ..config import OUTPUT_DIR


### Main Links Index

@enforce_types
def parse_sql_main_index(out_dir: Path=OUTPUT_DIR) -> Iterator[Link]:
    from core.models import Snapshot

    return (
        Link.from_json(page.as_json(*Snapshot.keys))
        for page in Snapshot.objects.all()
    )

@enforce_types
def remove_from_sql_main_index(snapshots: QuerySet, out_dir: Path=OUTPUT_DIR) -> None:
    with transaction.atomic():
        snapshots.delete()

@enforce_types
def write_link_to_sql_index(link: Link):
    from core.models import Snapshot, ArchiveResult
    info = {k: v for k, v in link._asdict().items() if k in Snapshot.keys}
    tags = info.pop("tags")
    if tags is None:
        tags = []

    try:
        info["timestamp"] = Snapshot.objects.get(url=link.url).timestamp
    except Snapshot.DoesNotExist:
        while Snapshot.objects.filter(timestamp=info["timestamp"]).exists():
            info["timestamp"] = str(float(info["timestamp"]) + 1.0)

    snapshot, _ = Snapshot.objects.update_or_create(url=link.url, defaults=info)
    snapshot.save_tags(tags)

    for extractor, entries in link.history.items():
        for entry in entries:
            if isinstance(entry, dict):
                result, _ = ArchiveResult.objects.get_or_create(
                    snapshot_id=snapshot.id,
                    extractor=extractor,
                    start_ts=parse_date(entry['start_ts']),
                    defaults={
                        'end_ts': parse_date(entry['end_ts']),
                        'cmd': entry['cmd'],
                        'output': entry['output'],
                        'cmd_version': entry.get('cmd_version') or 'unknown',
                        'pwd': entry['pwd'],
                        'status': entry['status'],
                    }
                )
            else:
                result, _ = ArchiveResult.objects.get_or_create(
                    snapshot_id=snapshot.id,
                    extractor=extractor,
                    start_ts=parse_date(entry.start_ts),
                    defaults={
                        'end_ts': parse_date(entry.end_ts),
                        'cmd': entry.cmd,
                        'output': entry.output,
                        'cmd_version': entry.cmd_version or 'unknown',
                        'pwd': entry.pwd,
                        'status': entry.status,
                    }
                )

            print(result)

    return snapshot


@enforce_types
def write_sql_main_index(links: List[Link], out_dir: Path=OUTPUT_DIR) -> None:
    with transaction.atomic():
        for link in links:
            write_link_to_sql_index(link)
            

@enforce_types
def write_sql_link_details(link: Link, out_dir: Path=OUTPUT_DIR) -> None:
    from core.models import Snapshot

    with transaction.atomic():
        try:
            snap = Snapshot.objects.get(url=link.url)
        except Snapshot.DoesNotExist:
            snap = write_link_to_sql_index(link)
        snap.title = link.title

        tag_set = (
            set(tag.strip() for tag in (link.tags or '').split(','))
        )
        tag_list = list(tag_set) or []

        snap.save()
        snap.save_tags(tag_list)



@enforce_types
def list_migrations(out_dir: Path=OUTPUT_DIR) -> List[Tuple[bool, str]]:
    from django.core.management import call_command
    out = StringIO()
    call_command("showmigrations", list=True, stdout=out)
    out.seek(0)
    migrations = []
    for line in out.readlines():
        if line.strip() and ']' in line:
            status_str, name_str = line.strip().split(']', 1)
            is_applied = 'X' in status_str
            migration_name = name_str.strip()
            migrations.append((is_applied, migration_name))

    return migrations

@enforce_types
def apply_migrations(out_dir: Path=OUTPUT_DIR) -> List[str]:
    from django.core.management import call_command
    null, out = StringIO(), StringIO()
    call_command("makemigrations", interactive=False, stdout=null)
    call_command("migrate", interactive=False, stdout=out)
    out.seek(0)

    return [line.strip() for line in out.readlines() if line.strip()]

@enforce_types
def get_admins(out_dir: Path=OUTPUT_DIR) -> List[str]:
    from django.contrib.auth.models import User
    return User.objects.filter(is_superuser=True)
