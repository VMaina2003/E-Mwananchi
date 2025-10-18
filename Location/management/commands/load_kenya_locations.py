import json
from django.core.management.base import BaseCommand
from Location.models import County, SubCounty, Ward


class Command(BaseCommand):
    help = "Load Kenya counties, subcounties, and wards from a PHPMyAdmin-exported JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="Kenya_counties.json",
            help="Path to Kenya_counties.json file"
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        self.stdout.write(self.style.MIGRATE_HEADING(f" Loading data from: {file_path}"))

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f"Invalid JSON format"))
            return

        # Extract tables
        counties_table = next((t for t in data if t.get("name") == "counties"), None)
        subcounties_table = next((t for t in data if t.get("name") == "subcounties"), None)
        stations_table = next((t for t in data if t.get("name") == "station"), None)

        if not counties_table or not subcounties_table or not stations_table:
            self.stderr.write(self.style.ERROR("Missing required tables (counties, subcounties, or stations)."))
            return

        counties = counties_table.get("data", [])
        subcounties = subcounties_table.get("data", [])
        stations = stations_table.get("data", [])

        county_count, subcounty_count, ward_count = 0, 0, 0

        # Step 1: Load Counties
        for c in counties:
            county, created = County.objects.get_or_create(
                code=c["county_id"],
                defaults={"name": c["county_name"].title()}
            )
            if created:
                county_count += 1

        # Step 2: Load Subcounties
        for s in subcounties:
            county = County.objects.filter(code=s["county_id"]).first()
            if county:
                subcounty, created = SubCounty.objects.get_or_create(
                    county=county,
                    name=s["constituency_name"].title(),
                    defaults={"code": s["subcounty_id"]}
                )
                if created:
                    subcounty_count += 1

        # Step 3: Load Wards (from "station" table)
        for w in stations:
            subcounty = SubCounty.objects.filter(code=w["subcounty_id"]).first()
            if subcounty and w.get("ward"):
                Ward.objects.get_or_create(
                    subcounty=subcounty,
                    name=w["ward"].title()
                )
                ward_count += 1

        self.stdout.write(self.style.SUCCESS(
            f" Done! Imported {county_count} counties, {subcounty_count} subcounties, {ward_count} wards."
        ))
