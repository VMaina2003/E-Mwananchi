import json
from django.core.management.base import BaseCommand
from Location.models import County, SubCounty, Ward


class Command(BaseCommand):
    help = "Loads Kenya counties, subcounties, and wards from Kenya_counties.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="Kenya_counties.json",
            help="Path to Kenya_counties.json file",
        )

    def handle(self, *args, **options):
        file_path = options["file"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"q Loading data from: {file_path}"))

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f"Invalid JSON format in {file_path}"))
            return

        # Expected structure: {"counties": [{...}], "subcounties": [{...}], "wards": [{...}]}
        counties = data.get("counties", [])
        subcounties = data.get("subcounties", [])
        wards = data.get("wards", [])

        # 1️ Load counties
        self.stdout.write(self.style.MIGRATE_LABEL("→ Loading counties..."))
        for c in counties:
            county, created = County.objects.get_or_create(
                code=c.get("county_id"),
                defaults={
                    "name": c.get("county_name"),
                    "capital": c.get("capital") or "",
                },
            )
            if not created:
                county.name = c.get("county_name")
                county.save()

        # 2️ Load subcounties
        self.stdout.write(self.style.MIGRATE_LABEL("→ Loading subcounties..."))
        for s in subcounties:
            county = County.objects.filter(code=s.get("county_id")).first()
            if not county:
                continue

            SubCounty.objects.get_or_create(
                county=county,
                name=s.get("constituency_name"),
                defaults={
                    "code": s.get("subcounty_id"),
                },
            )

        # 3️ Load wards
        self.stdout.write(self.style.MIGRATE_LABEL("→ Loading wards..."))
        for w in wards:
            subcounty = SubCounty.objects.filter(name=w.get("constituency_name")).first()
            if not subcounty:
                continue

            Ward.objects.get_or_create(
                subcounty=subcounty,
                name=w.get("ward"),
            )

        self.stdout.write(self.style.SUCCESS(" Kenya counties, subcounties, and wards loaded successfully!"))
