"""
================================================================================
TRACKER - DATABASE SCHEMA AND OPERATIONS
================================================================================
Event-centric case management and digital footprint tracking for OSINT
investigations and law enforcement case management.

This module provides the complete database layer for the Tracker application,
handling all CRUD operations, entity relationships, and data queries.

DATABASE ARCHITECTURE:
----------------------
The database uses a relational model with the following core entities:
- Subjects: People/persons of interest
- Gangs: Criminal organizations
- Locations: Addresses, residences, territories
- Events: Incidents, calls for service, investigations

Entity relationships are managed through linking tables that allow
many-to-many relationships between all entity types.

SECURITY NOTE:
--------------
This database may contain sensitive PII (Personally Identifiable Information)
and law enforcement intelligence data. Ensure proper access controls and
encryption at rest when deployed.

SQL INJECTION PREVENTION:
-------------------------
All database queries use parameterized statements (? placeholders).
No string concatenation is used in SQL queries.

================================================================================
"""

import sqlite3
import os
from datetime import datetime
import shutil
import uuid

class TrackerDB:
    """
    Main database interface for the Tracker application.

    This class provides all database operations including:
    - Table creation and schema management
    - CRUD operations for all entity types
    - Relationship linking between entities
    - Complex queries for profile compilation
    - Graph data generation for visualization
    - Checklist management for OSINT workflows

    Attributes:
        db_path (str): Path to the SQLite database file
        conn (sqlite3.Connection): Active database connection

    Example Usage:
        >>> db = TrackerDB("data/database.db")
        >>> subject_id = db.add_subject("John", "Doe", dob="1990-01-15")
        >>> profile = db.get_subject_full_profile(subject_id)
        >>> db.close()
    """

    def __init__(self, db_path: str = "data/database.db"):
        """
        Initialize the database connection and ensure all tables exist.

        Args:
            db_path: Path to the SQLite database file. Will be created if
                    it doesn't exist. Parent directories are created automatically.

        The initialization process:
        1. Creates the data directory if needed
        2. Establishes database connection
        3. Enables foreign key constraints
        4. Creates all required tables
        5. Populates default checklist items if empty
        """
        self.db_path = db_path
        self.conn = None
        self.ensure_directory()
        self.connect()
        self.create_tables()

    def ensure_directory(self):
        """
        Create the data directory structure if it doesn't exist.

        This ensures the parent directory for the database file exists,
        preventing errors on first run.
        """
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def connect(self):
        """
        Establish connection to the SQLite database.

        Configuration:
        - Row factory set to sqlite3.Row for dict-like access
        - Foreign key constraints enabled for referential integrity
        """
        self.conn = sqlite3.connect(self.db_path)
        # Enable dict-like access to rows (row['column_name'])
        self.conn.row_factory = sqlite3.Row
        # Enable foreign key enforcement for cascading deletes
        self.conn.execute("PRAGMA foreign_keys = ON")

    def create_tables(self):
        """
        Create all database tables if they don't already exist.

        TABLE STRUCTURE OVERVIEW:

        PRIMARY ENTITIES:
        -----------------
        subjects        - People/persons of interest with full PII
        gangs           - Criminal organizations and groups
        locations       - Physical addresses and places
        events          - Incidents, calls, investigations
        vehicles        - Cars, trucks, motorcycles
        weapons         - Firearms and other weapons

        LINKING TABLES (Many-to-Many Relationships):
        -------------------------------------------
        subject_gangs       - Subject membership in gangs
        subject_locations   - Subject addresses/associations
        subject_events      - Subject involvement in events
        subject_vehicles    - Subject vehicle ownership/use
        subject_weapons     - Subject weapon possession
        subject_associations - Direct subject-to-subject links
        gang_events         - Gang involvement in events
        gang_locations      - Gang territories/hangouts
        event_vehicles      - Vehicles involved in events
        event_weapons       - Weapons involved in events

        DETAIL TABLES (One-to-Many from Subjects):
        -----------------------------------------
        social_profiles     - Social media accounts
        phone_numbers       - Contact numbers
        emails              - Email addresses
        family_members      - Family relationships
        tattoos             - Physical identifiers
        case_numbers        - Court case references

        INTEL TABLES:
        -------------
        charges         - Criminal charges/arrests
        charge_affiliates - Co-defendants on charges
        graffiti        - Gang graffiti sightings
        intel_reports   - Intelligence reports
        evidence        - Physical evidence from events
        media           - Photos/documents for any entity

        WORKFLOW TABLES:
        ----------------
        checklist_items     - OSINT checklist templates
        checklist_progress  - Per-subject checklist tracking
        """
        cursor = self.conn.cursor()

        # =====================================================================
        # SUBJECTS TABLE - Primary person/POI records
        # =====================================================================
        # Stores all identifying information for persons of interest including
        # PII (SSN, DOB, OLN), physical descriptors, and intelligence notes.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                first_name TEXT,                  -- Legal first name
                last_name TEXT,                   -- Legal last name
                dob TEXT,                         -- Date of birth (YYYY-MM-DD)
                ssn TEXT,                         -- Social Security Number
                oln TEXT,                         -- Operator License Number (DL)
                scope_id TEXT,                    -- State ID number (legacy column name)
                monikers TEXT,                    -- Aliases, nicknames, street names
                -- Physical Descriptors for identification
                height TEXT,                      -- Height (e.g., "5'10\"")
                weight TEXT,                      -- Weight in pounds
                hair_color TEXT,                  -- Hair color
                eye_color TEXT,                   -- Eye color
                build TEXT,                       -- Body build (slim, medium, heavy)
                race TEXT,                        -- Race/ethnicity
                sex TEXT,                         -- Sex (M/F)
                -- Intelligence fields
                mo TEXT,                          -- Modus Operandi
                criminal_history TEXT,            -- Summary of criminal history
                case_number TEXT,                 -- Primary case number reference
                rissafe_id TEXT,                  -- RISSAFE system ID
                notes TEXT,                       -- General notes
                profile_photo TEXT,               -- Path to profile photo
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =====================================================================
        # GANGS TABLE - Criminal organization records
        # =====================================================================
        # Tracks gangs, crews, and criminal organizations with their identifiers
        # and known territories.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gangs (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                name TEXT NOT NULL,               -- Gang name/set
                details TEXT,                     -- General information
                history TEXT,                     -- Historical background
                territory TEXT,                   -- Known territory description
                identifiers TEXT,                 -- Colors, signs, tattoos
                notes TEXT,                       -- Additional notes
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =====================================================================
        # LOCATIONS TABLE - Physical addresses and places
        # =====================================================================
        # Stores addresses with optional geocoding for map integration.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                address TEXT NOT NULL,            -- Full street address
                type TEXT,                        -- Type: residence, business, etc.
                description TEXT,                 -- Location description
                rissafe_id TEXT,                  -- RISSAFE location ID
                notes TEXT,                       -- Additional notes
                lat TEXT,                         -- Latitude for mapping
                lon TEXT,                         -- Longitude for mapping
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =====================================================================
        # EVENTS TABLE - Incidents, calls, investigations
        # =====================================================================
        # Central table for all events/incidents. Events serve as the primary
        # entry point linking subjects, locations, vehicles, and weapons.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                event_number TEXT,                -- CAD/RMS event number
                event_date TEXT,                  -- Date of event (YYYY-MM-DD)
                event_type TEXT,                  -- Type: arrest, FI, traffic, etc.
                location_id TEXT,                 -- FK to locations table
                location_text TEXT,               -- Freetext location if not linked
                generated_source TEXT,            -- How event was generated
                code_400 TEXT,                    -- Disposition/400 code
                details TEXT,                     -- Event narrative
                case_notes TEXT,                  -- Investigator notes
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
            )
        """)

        # =====================================================================
        # LINKING TABLES - Entity Relationships
        # =====================================================================

        # Subject to Gang membership
        # Tracks which subjects are affiliated with which gangs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_gangs (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                gang_id TEXT NOT NULL,
                role TEXT,                        -- Role: member, associate, leader
                status TEXT DEFAULT 'active',     -- Status: active, inactive, former
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (gang_id) REFERENCES gangs(id) ON DELETE CASCADE,
                UNIQUE(subject_id, gang_id)       -- Prevent duplicate links
            )
        """)

        # Subject to Location associations
        # Links subjects to addresses (residences, frequented locations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_locations (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                location_id TEXT NOT NULL,
                relationship TEXT,                -- Relationship to location
                is_primary_residence INTEGER DEFAULT 0,  -- 1 if primary address
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
                UNIQUE(subject_id, location_id)
            )
        """)

        # Subject to Event involvement
        # Links subjects to events with their role in the event
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_events (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                role TEXT,                        -- Role: suspect, victim, witness, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                UNIQUE(subject_id, event_id)
            )
        """)

        # Gang to Event involvement
        # Links gangs to events they were involved in
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gang_events (
                id TEXT PRIMARY KEY,
                gang_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gang_id) REFERENCES gangs(id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                UNIQUE(gang_id, event_id)
            )
        """)

        # Gang to Location (territory/hangouts)
        # Marks locations as gang territory or hangouts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gang_locations (
                id TEXT PRIMARY KEY,
                gang_id TEXT NOT NULL,
                location_id TEXT NOT NULL,
                relationship TEXT,                -- Type: territory, hangout, trap, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gang_id) REFERENCES gangs(id) ON DELETE CASCADE,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
                UNIQUE(gang_id, location_id)
            )
        """)

        # Direct subject-to-subject associations
        # Links two subjects directly (associates, co-conspirators)
        # Uses ordered IDs to prevent duplicate entries (A-B and B-A)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_associations (
                id TEXT PRIMARY KEY,
                subject1_id TEXT NOT NULL,        -- Lower ID always first
                subject2_id TEXT NOT NULL,        -- Higher ID always second
                relationship TEXT,                -- Type: associate, co-defendant, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject1_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (subject2_id) REFERENCES subjects(id) ON DELETE CASCADE,
                UNIQUE(subject1_id, subject2_id)
            )
        """)

        # =====================================================================
        # SUBJECT DETAIL TABLES - Contact info, identifiers
        # =====================================================================

        # Social media profiles
        # Stores social media accounts for OSINT tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS social_profiles (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                platform TEXT NOT NULL,           -- Platform: Facebook, Instagram, etc.
                username TEXT,                    -- Username on platform
                url TEXT,                         -- Direct URL to profile
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # Phone numbers
        # Multiple phone numbers per subject with type classification
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phone_numbers (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                number TEXT NOT NULL,             -- Phone number
                phone_type TEXT,                  -- Type: cell, home, work, burner
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # Email addresses
        # Multiple email addresses per subject
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                email TEXT NOT NULL,              -- Email address
                email_type TEXT,                  -- Type: personal, work, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # Family relationships
        # Links subjects to family members (can link to other subjects)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS family_members (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                family_member_id TEXT,            -- FK to subjects if in database
                family_name TEXT,                 -- Name if not in database
                relationship TEXT NOT NULL,       -- Type: mother, father, spouse, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (family_member_id) REFERENCES subjects(id) ON DELETE SET NULL
            )
        """)

        # Media/Evidence files
        # Generic media storage linking to any entity type
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,        -- Type: subject, gang, event, etc.
                entity_id TEXT NOT NULL,          -- ID of the linked entity
                file_path TEXT NOT NULL,          -- Path to media file
                file_type TEXT,                   -- MIME type or extension
                title TEXT,                       -- Display title
                description TEXT,                 -- Description of media
                is_pinned INTEGER DEFAULT 0,      -- 1 if pinned for bubble display
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: Add is_pinned column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE media ADD COLUMN is_pinned INTEGER DEFAULT 0")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

        # =====================================================================
        # TATTOOS TABLE - Physical identifiers for subjects
        # =====================================================================
        # Tracks tattoos with location, description, and gang affiliation flag
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tattoos (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                description TEXT,                 -- What the tattoo depicts
                body_location TEXT,               -- Where on body: left arm, etc.
                is_gang_affiliated INTEGER DEFAULT 0,  -- 1 if gang-related
                photo_path TEXT,                  -- Path to tattoo photo
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # =====================================================================
        # VEHICLES TABLE - Vehicle records
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id TEXT PRIMARY KEY,
                plate TEXT,                       -- License plate number
                state TEXT,                       -- Registration state
                make TEXT,                        -- Vehicle make (Ford, etc.)
                model TEXT,                       -- Vehicle model
                year TEXT,                        -- Model year
                color TEXT,                       -- Vehicle color
                vin TEXT,                         -- Vehicle Identification Number
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Subject to Vehicle relationships
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_vehicles (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                relationship TEXT,                -- Type: owner, driver, passenger
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
                UNIQUE(subject_id, vehicle_id)
            )
        """)

        # Event to Vehicle (vehicles involved in events)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_vehicles (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
                UNIQUE(event_id, vehicle_id)
            )
        """)

        # =====================================================================
        # WEAPONS TABLE - Firearm and weapon records
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weapons (
                id TEXT PRIMARY KEY,
                weapon_type TEXT,                 -- Type: handgun, rifle, knife, etc.
                make TEXT,                        -- Manufacturer
                model TEXT,                       -- Model name
                caliber TEXT,                     -- Caliber/gauge
                serial_number TEXT,               -- Serial number
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Subject to Weapon relationships
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_weapons (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                weapon_id TEXT NOT NULL,
                relationship TEXT,                -- Type: owner, possessed, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (weapon_id) REFERENCES weapons(id) ON DELETE CASCADE,
                UNIQUE(subject_id, weapon_id)
            )
        """)

        # Event to Weapon (weapons involved in events)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_weapons (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                weapon_id TEXT NOT NULL,
                disposition TEXT,                 -- What happened: seized, used, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (weapon_id) REFERENCES weapons(id) ON DELETE CASCADE,
                UNIQUE(event_id, weapon_id)
            )
        """)

        # =====================================================================
        # EVIDENCE TABLE - Physical evidence from events
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                description TEXT,                 -- What the evidence is
                evidence_type TEXT,               -- Type: physical, digital, etc.
                location_found TEXT,              -- Where it was found
                disposition TEXT,                 -- What happened to it
                photo_path TEXT,                  -- Photo of evidence
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)

        # =====================================================================
        # CHARGES TABLE - Criminal charges and arrests
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS charges (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,         -- Who was charged
                event_id TEXT,                    -- Related event if any
                charges_text TEXT,                -- Charge description/statute
                charge_date TEXT,                 -- Date of charge
                location_id TEXT,                 -- Where charge occurred
                location_text TEXT,               -- Freetext location
                court_case_number TEXT,           -- Court case number
                court_url TEXT,                   -- URL to court records
                gang_id TEXT,                     -- Related gang if any
                details TEXT,                     -- Charge details
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL,
                FOREIGN KEY (gang_id) REFERENCES gangs(id) ON DELETE SET NULL
            )
        """)

        # Charge affiliates (co-defendants)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS charge_affiliates (
                id TEXT PRIMARY KEY,
                charge_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,         -- Co-defendant
                role TEXT,                        -- Role in charge
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (charge_id) REFERENCES charges(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                UNIQUE(charge_id, subject_id)
            )
        """)

        # =====================================================================
        # GRAFFITI TABLE - Gang graffiti documentation
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graffiti (
                id TEXT PRIMARY KEY,
                location_id TEXT,                 -- FK to locations
                location_text TEXT,               -- Freetext location
                tags TEXT,                        -- What was written/drawn
                gang_id TEXT,                     -- Attributed gang
                monikers TEXT,                    -- Monikers in graffiti
                sector_beat TEXT,                 -- Police sector/beat
                area_command TEXT,                -- Area command
                date_observed TEXT,               -- When observed
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL,
                FOREIGN KEY (gang_id) REFERENCES gangs(id) ON DELETE SET NULL
            )
        """)

        # =====================================================================
        # INTEL REPORTS TABLE - Intelligence reports
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intel_reports (
                id TEXT PRIMARY KEY,
                report_date TEXT,                 -- Date of report
                source_type TEXT,                 -- Source: CI, social media, etc.
                reliability TEXT,                 -- Source reliability rating
                details TEXT,                     -- Intelligence content
                subject_id TEXT,                  -- Related subject
                gang_id TEXT,                     -- Related gang
                location_id TEXT,                 -- Related location
                event_id TEXT,                    -- Related event
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
                FOREIGN KEY (gang_id) REFERENCES gangs(id) ON DELETE SET NULL,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL
            )
        """)

        # =====================================================================
        # CASE NUMBERS TABLE - Court case tracking
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_numbers (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                case_number TEXT NOT NULL,        -- Court case number
                case_type TEXT,                   -- Type: criminal, civil, etc.
                court TEXT,                       -- Which court
                status TEXT,                      -- Case status
                url TEXT,                         -- URL to case info
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # =====================================================================
        # STATE IDS TABLE - Government-issued identification numbers
        # =====================================================================
        # Tracks State IDs, RISSAFE IDs, and other government IDs per subject
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_ids (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                id_number TEXT NOT NULL,          -- The ID number
                id_type TEXT,                     -- Type: State ID, RISSAFE, FBI#, etc.
                state TEXT,                       -- Issuing state (e.g. NV, CA)
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # =====================================================================
        # EMPLOYMENT TABLE - Employment and business affiliations
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employment (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                employer TEXT NOT NULL,           -- Employer or business name
                position TEXT,                    -- Job title/position
                address TEXT,                     -- Work address
                phone TEXT,                       -- Work phone
                start_date TEXT,                  -- Employment start
                end_date TEXT,                    -- Employment end (blank if current)
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # =====================================================================
        # CHECKLIST ITEMS TABLE - OSINT workflow templates
        # =====================================================================
        # Stores the master list of OSINT sources to check for each subject
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checklist_items (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,           -- Category: LE Databases, Social, etc.
                name TEXT NOT NULL,               -- Item name
                url TEXT,                         -- URL to open
                description TEXT,                 -- How to use this source
                sort_order INTEGER DEFAULT 0,     -- Display order
                is_default INTEGER DEFAULT 0,     -- 1 if system default
                is_active INTEGER DEFAULT 1,      -- 0 if hidden
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =====================================================================
        # CHECKLIST PROGRESS TABLE - Per-subject tracking
        # =====================================================================
        # Tracks which checklist items have been completed for each subject
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checklist_progress (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                checklist_item_id TEXT NOT NULL,
                completed INTEGER DEFAULT 0,      -- 1 if completed
                completed_date TEXT,              -- When completed
                result_notes TEXT,                -- What was found
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE,
                UNIQUE(subject_id, checklist_item_id)
            )
        """)

        # =====================================================================
        # ONLINE ACCOUNTS TABLE - Social media and website profiles
        # =====================================================================
        # Track accounts even before they're linked to identified subjects
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS online_accounts (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                platform TEXT NOT NULL,           -- Twitter, Instagram, TikTok, etc.
                platform_account_id TEXT,         -- Permanent ID from platform
                username TEXT,                    -- Current username/handle
                display_name TEXT,                -- Current display name
                profile_url TEXT,                 -- Full URL to profile
                account_type TEXT DEFAULT 'Unknown',  -- Personal, Business, Bot, Unknown
                status TEXT DEFAULT 'Active',     -- Active, Suspended, Deleted, Private
                subject_id TEXT,                  -- Optional FK to subjects
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL
            )
        """)

        # =====================================================================
        # ACCOUNT POSTS TABLE - Posts and activity from tracked accounts
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_posts (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                account_id TEXT NOT NULL,         -- FK to online_accounts
                title TEXT,                       -- User-defined title for easy identification
                post_date TEXT,                   -- When the post was made
                captured_date TEXT,               -- When we captured/screenshotted it
                post_url TEXT,                    -- Direct link to post
                post_type TEXT DEFAULT 'Post',    -- Post, Comment, Story, Reel, Message, Listing
                content_text TEXT,                -- Text content of post
                activity_type TEXT,               -- Drug Sale, Weapon Sale, Threat, etc.
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES online_accounts(id) ON DELETE CASCADE
            )
        """)

        # Add title column to existing account_posts tables
        try:
            cursor.execute("ALTER TABLE account_posts ADD COLUMN title TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # =====================================================================
        # DNS INVESTIGATIONS TABLE - Domain and DNS record tracking
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dns_investigations (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                domain_name TEXT NOT NULL,        -- The domain being investigated
                investigation_date TEXT,          -- When lookup was performed
                a_records TEXT,                   -- IPv4 addresses (JSON array)
                aaaa_records TEXT,                -- IPv6 addresses (JSON array)
                mx_records TEXT,                  -- Mail servers (JSON array)
                txt_records TEXT,                 -- TXT records (JSON array)
                cname_records TEXT,               -- Canonical names (JSON array)
                ns_records TEXT,                  -- Nameservers (JSON array)
                registrar TEXT,                   -- Domain registrar
                registrant_name TEXT,             -- WHOIS registrant
                registrant_email TEXT,            -- WHOIS email
                registration_date TEXT,           -- When domain was registered
                expiration_date TEXT,             -- When domain expires
                hosting_provider TEXT,            -- Identified hosting provider
                ip_addresses TEXT,                -- Associated IPs (JSON array)
                subject_id TEXT,                  -- Optional FK to subjects
                account_id TEXT,                  -- Optional FK to online_accounts
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
                FOREIGN KEY (account_id) REFERENCES online_accounts(id) ON DELETE SET NULL
            )
        """)

        # =====================================================================
        # CUSTOM LINKS TABLE - Arbitrary entity linkage
        # =====================================================================
        # Catch-all for linking arbitrary information to any entity type
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_links (
                id TEXT PRIMARY KEY,              -- UUID (8 chars)
                link_type TEXT,                   -- User-defined type (Evidence, Related Case, etc.)
                title TEXT NOT NULL,              -- Short title
                description TEXT,                 -- Detailed description
                url TEXT,                         -- Optional URL
                entity_type TEXT NOT NULL,        -- What it's linked to (subject, event, etc.)
                entity_id TEXT NOT NULL,          -- ID of linked entity
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =====================================================================
        # ACCOUNT ASSOCIATIONS TABLE - Link online accounts together
        # =====================================================================
        # Like subject_associations but for online accounts
        # Example: Multiple accounts promoting same event/product
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_associations (
                id TEXT PRIMARY KEY,
                account1_id TEXT NOT NULL,
                account2_id TEXT NOT NULL,
                association_type TEXT,            -- Promoting same content, Same person, Coordinated activity, etc.
                evidence TEXT,                    -- Description of why they're linked
                confidence TEXT DEFAULT 'Medium', -- Low, Medium, High, Confirmed
                discovered_date TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account1_id) REFERENCES online_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY (account2_id) REFERENCES online_accounts(id) ON DELETE CASCADE,
                UNIQUE(account1_id, account2_id)
            )
        """)

        # =====================================================================
        # ACCOUNT VEHICLES TABLE - Link vehicles to online accounts
        # =====================================================================
        # Example: Vehicle shown in social media posts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_vehicles (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                relationship TEXT,                 -- Driven in video, For sale, Pictured with, etc.
                evidence TEXT,                     -- Where/how this link was found
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES online_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
                UNIQUE(account_id, vehicle_id)
            )
        """)

        # =====================================================================
        # TRACKED PHONES TABLE - Phone numbers before linked to subjects
        # =====================================================================
        # Like online_accounts but for phone numbers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_phones (
                id TEXT PRIMARY KEY,
                phone_number TEXT NOT NULL,
                phone_type TEXT DEFAULT 'Unknown',    -- Cell, Landline, VoIP, Burner, Unknown
                carrier TEXT,                         -- Carrier name if known
                carrier_type TEXT,                    -- Wireless, Landline, VoIP
                location_area TEXT,                   -- City/State from area code
                status TEXT DEFAULT 'Active',         -- Active, Disconnected, Unknown
                registered_name TEXT,                 -- Name from carrier lookup
                first_seen_date TEXT,                 -- When we first encountered it
                last_seen_date TEXT,                  -- Most recent activity
                subject_id TEXT,                      -- Optional FK to subjects
                account_id TEXT,                      -- Optional FK to online_accounts (linked social)
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
                FOREIGN KEY (account_id) REFERENCES online_accounts(id) ON DELETE SET NULL
            )
        """)

        # =====================================================================
        # ENTITY LINKS TABLE - Universal entity-to-entity linking
        # =====================================================================
        # Allows linking ANY entity type to ANY other entity type
        # This is the "spider web" builder - makes connections without specific junction tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_links (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,        -- Entity type (subject, vehicle, online_account, etc.)
                source_id TEXT NOT NULL,          -- ID of source entity
                target_type TEXT NOT NULL,        -- Entity type of linked entity
                target_id TEXT NOT NULL,          -- ID of linked entity
                relationship TEXT,                -- User-defined relationship type
                direction TEXT DEFAULT 'both',    -- 'forward', 'reverse', 'both' (bidirectional)
                evidence TEXT,                    -- Evidence/proof of connection
                confidence TEXT DEFAULT 'Medium', -- Low, Medium, High, Confirmed
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_type, source_id, target_type, target_id)
            )
        """)

        # Commit all table creations
        self.conn.commit()

        # Insert default checklist items if the table is empty
        cursor.execute("SELECT COUNT(*) FROM checklist_items")
        if cursor.fetchone()[0] == 0:
            self._insert_default_checklist_items()

    # =========================================================================
    # SUBJECT OPERATIONS
    # =========================================================================
    # Methods for creating, reading, updating, and deleting subject records

    def add_subject(self, first_name: str, last_name: str, **kwargs) -> str:
        """
        Create a new subject record in the database.

        Args:
            first_name: Subject's first name
            last_name: Subject's last name
            **kwargs: Optional fields including:
                - dob: Date of birth (YYYY-MM-DD)
                - ssn: Social Security Number
                - oln: Driver's License Number
                - scope_id: SCOPE system ID
                - monikers: Aliases/nicknames
                - height, weight, hair_color, eye_color, build, race, sex
                - mo: Modus Operandi
                - criminal_history: Summary of criminal history
                - case_number: Primary case reference
                - rissafe_id: RISSAFE ID
                - notes: General notes
                - profile_photo: Path to photo file

        Returns:
            str: The unique 8-character ID assigned to the new subject

        Side Effects:
            - Creates a media directory for the subject at data/media/subjects/{id}/
        """
        # Generate unique 8-character ID from UUID
        subject_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO subjects (id, first_name, last_name, dob, ssn, oln, scope_id,
                                  monikers, height, weight, hair_color, eye_color, build, race, sex,
                                  mo, criminal_history, case_number, rissafe_id, notes, profile_photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            subject_id,
            first_name,
            last_name,
            kwargs.get('dob', ''),
            kwargs.get('ssn', ''),
            kwargs.get('oln', ''),
            kwargs.get('scope_id', ''),
            kwargs.get('monikers', ''),
            kwargs.get('height', ''),
            kwargs.get('weight', ''),
            kwargs.get('hair_color', ''),
            kwargs.get('eye_color', ''),
            kwargs.get('build', ''),
            kwargs.get('race', ''),
            kwargs.get('sex', ''),
            kwargs.get('mo', ''),
            kwargs.get('criminal_history', ''),
            kwargs.get('case_number', ''),
            kwargs.get('rissafe_id', ''),
            kwargs.get('notes', ''),
            kwargs.get('profile_photo', '')
        ))

        self.conn.commit()
        # Create media storage directory for this subject
        os.makedirs(f"data/media/subjects/{subject_id}", exist_ok=True)
        return subject_id

    def get_subject(self, subject_id: str) -> dict:
        """
        Retrieve a single subject record by ID.

        Args:
            subject_id: The unique identifier of the subject

        Returns:
            dict: Subject data as a dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_subjects(self) -> list:
        """
        Retrieve all subject records, ordered by name.

        Returns:
            list: List of subject dictionaries, sorted by last_name, first_name
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subjects ORDER BY last_name, first_name")
        return [dict(row) for row in cursor.fetchall()]

    def update_subject(self, subject_id: str, **kwargs):
        """
        Update an existing subject's information.

        Only provided fields will be updated. The updated_at timestamp
        is automatically set to the current time.

        Args:
            subject_id: The unique identifier of the subject to update
            **kwargs: Fields to update (same as add_subject)

        Note:
            Only fields in the allowed list will be updated to prevent
            SQL injection via field names.
        """
        cursor = self.conn.cursor()
        # Whitelist of allowed fields to update
        allowed = ['first_name', 'last_name', 'dob', 'ssn', 'oln', 'scope_id',
                   'monikers', 'height', 'weight', 'hair_color', 'eye_color', 'build', 'race', 'sex',
                   'mo', 'criminal_history', 'case_number', 'rissafe_id', 'notes', 'profile_photo']

        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)

        if updates:
            # Always update the timestamp
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(subject_id)
            cursor.execute(f"UPDATE subjects SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def delete_subject(self, subject_id: str):
        """
        Delete a subject and all associated data.

        Due to CASCADE constraints, this will also delete:
        - All linking table entries (gang affiliations, events, etc.)
        - Social profiles, phone numbers, emails
        - Family member entries
        - Tattoo records
        - Media files in the subject's directory

        Args:
            subject_id: The unique identifier of the subject to delete
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        self.conn.commit()
        # Remove subject's media directory
        media_path = f"data/media/subjects/{subject_id}"
        if os.path.exists(media_path):
            shutil.rmtree(media_path)

    def search_subjects(self, query: str) -> list:
        """
        Search for subjects matching a query string.

        Searches across multiple fields: first_name, last_name, monikers,
        ssn, oln, and scope_id using case-insensitive partial matching.

        Args:
            query: Search string to match

        Returns:
            list: List of matching subject dictionaries
        """
        cursor = self.conn.cursor()
        search = f"%{query}%"
        cursor.execute("""
            SELECT * FROM subjects
            WHERE first_name LIKE ? OR last_name LIKE ? OR monikers LIKE ?
                  OR ssn LIKE ? OR oln LIKE ? OR scope_id LIKE ?
            ORDER BY last_name, first_name
        """, (search, search, search, search, search, search))
        return [dict(row) for row in cursor.fetchall()]

    def find_or_create_subject(self, first_name: str, last_name: str, **kwargs) -> str:
        """
        Find an existing subject or create a new one.

        Attempts to find a matching subject using:
        1. SSN match (most unique identifier)
        2. Name + DOB match

        If no match is found, creates a new subject.

        Args:
            first_name: Subject's first name
            last_name: Subject's last name
            **kwargs: Additional fields (same as add_subject)

        Returns:
            str: ID of the found or newly created subject
        """
        cursor = self.conn.cursor()

        # Try to find by SSN first (most unique identifier)
        if kwargs.get('ssn'):
            cursor.execute("SELECT id FROM subjects WHERE ssn = ?", (kwargs['ssn'],))
            row = cursor.fetchone()
            if row:
                return row['id']

        # Try to find by name + DOB
        if kwargs.get('dob'):
            cursor.execute("""
                SELECT id FROM subjects
                WHERE first_name = ? AND last_name = ? AND dob = ?
            """, (first_name, last_name, kwargs['dob']))
            row = cursor.fetchone()
            if row:
                return row['id']

        # Create new subject
        return self.add_subject(first_name, last_name, **kwargs)

    # =========================================================================
    # GANG OPERATIONS
    # =========================================================================

    def add_gang(self, name: str, **kwargs) -> str:
        """
        Create a new gang/organization record.

        Args:
            name: Gang name/set name
            **kwargs: Optional fields:
                - details: General information
                - history: Historical background
                - territory: Territory description
                - identifiers: Colors, signs, tattoos
                - notes: Additional notes

        Returns:
            str: The unique 8-character ID assigned to the new gang
        """
        gang_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO gangs (id, name, details, history, territory, identifiers, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            gang_id,
            name,
            kwargs.get('details', ''),
            kwargs.get('history', ''),
            kwargs.get('territory', ''),
            kwargs.get('identifiers', ''),
            kwargs.get('notes', '')
        ))

        self.conn.commit()
        os.makedirs(f"data/media/gangs/{gang_id}", exist_ok=True)
        return gang_id

    def get_gang(self, gang_id: str) -> dict:
        """
        Retrieve a single gang record by ID.

        Args:
            gang_id: The unique identifier of the gang

        Returns:
            dict: Gang data as a dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM gangs WHERE id = ?", (gang_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_gangs(self) -> list:
        """
        Retrieve all gang records, ordered alphabetically by name.

        Returns:
            list: List of gang dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM gangs ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def find_or_create_gang(self, name: str, **kwargs) -> str:
        """
        Find an existing gang by name or create a new one.

        Uses case-insensitive name matching.

        Args:
            name: Gang name to find or create
            **kwargs: Additional fields if creating new

        Returns:
            str: ID of the found or newly created gang
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM gangs WHERE LOWER(name) = LOWER(?)", (name,))
        row = cursor.fetchone()
        if row:
            return row['id']
        return self.add_gang(name, **kwargs)

    def update_gang(self, gang_id: str, **kwargs):
        """Update a gang record."""
        allowed = ['name', 'details', 'history', 'territory', 'identifiers', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE gangs SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [gang_id])
        self.conn.commit()

    def delete_gang(self, gang_id: str):
        """
        Delete a gang and all associated data.

        Cascading deletes will remove all member links and event associations.

        Args:
            gang_id: The unique identifier of the gang to delete
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM gangs WHERE id = ?", (gang_id,))
        self.conn.commit()

    # =========================================================================
    # LOCATION OPERATIONS
    # =========================================================================

    def add_location(self, address: str, **kwargs) -> str:
        """
        Create a new location record.

        Args:
            address: Full street address
            **kwargs: Optional fields:
                - type: Location type (residence, business, etc.)
                - description: Location description
                - rissafe_id: RISSAFE location ID
                - notes: Additional notes
                - lat: Latitude for mapping
                - lon: Longitude for mapping

        Returns:
            str: The unique 8-character ID assigned to the new location
        """
        location_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO locations (id, address, type, description, rissafe_id, notes, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            location_id,
            address,
            kwargs.get('type', ''),
            kwargs.get('description', ''),
            kwargs.get('rissafe_id', ''),
            kwargs.get('notes', ''),
            kwargs.get('lat', ''),
            kwargs.get('lon', '')
        ))

        self.conn.commit()
        os.makedirs(f"data/media/locations/{location_id}", exist_ok=True)
        return location_id

    def get_location(self, location_id: str) -> dict:
        """
        Retrieve a single location record by ID.

        Args:
            location_id: The unique identifier of the location

        Returns:
            dict: Location data as a dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_locations(self) -> list:
        """
        Retrieve all location records, ordered alphabetically by address.

        Returns:
            list: List of location dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM locations ORDER BY address")
        return [dict(row) for row in cursor.fetchall()]

    def find_existing_location(self, address: str) -> str | None:
        """
        Find an existing location by address (without creating).

        Uses case-insensitive matching with priority on street number + street name.
        Matching order:
        1. Exact full address match (case-insensitive)
        2. Street address match (number + street name, first part before comma)

        Args:
            address: Address to find (format: "1234 Main St, City, ST 12345")

        Returns:
            str | None: ID of the found location, or None if not found
        """
        cursor = self.conn.cursor()

        # First try exact full address match
        cursor.execute("SELECT id FROM locations WHERE LOWER(address) = LOWER(?)", (address,))
        row = cursor.fetchone()
        if row:
            return row['id']

        # Extract street address (number + street name) for matching
        # Format: "1234 Main St, City, ST 12345" -> "1234 Main St"
        street_part = address.split(',')[0].strip() if address else ""

        if street_part:
            # Try matching on street address only (case-insensitive)
            # This matches addresses with same street but different city/state/zip
            cursor.execute("""
                SELECT id FROM locations
                WHERE LOWER(address) LIKE LOWER(?) || ',%'
                   OR LOWER(address) = LOWER(?)
            """, (street_part, street_part))
            row = cursor.fetchone()
            if row:
                return row['id']

        return None

    def find_or_create_location(self, address: str, **kwargs) -> str:
        """
        Find an existing location by address or create a new one.

        Args:
            address: Address to find or create (format: "1234 Main St, City, ST 12345")
            **kwargs: Additional fields if creating new

        Returns:
            str: ID of the found or newly created location
        """
        existing_id = self.find_existing_location(address)
        if existing_id:
            return existing_id
        return self.add_location(address, **kwargs)

    def is_subject_linked_to_location(self, subject_id: str, location_id: str) -> bool:
        """Check if a subject is already linked to a location."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM subject_locations WHERE subject_id = ? AND location_id = ?",
            (subject_id, location_id)
        )
        return cursor.fetchone() is not None

    def is_gang_linked_to_location(self, gang_id: str, location_id: str) -> bool:
        """Check if a gang is already linked to a location."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM gang_locations WHERE gang_id = ? AND location_id = ?",
            (gang_id, location_id)
        )
        return cursor.fetchone() is not None

    def update_location(self, location_id: str, **kwargs):
        """Update a location record."""
        allowed = ['address', 'type', 'description', 'lat', 'lon', 'rissafe_id', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE locations SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [location_id])
        self.conn.commit()

    def delete_location(self, location_id: str):
        """
        Delete a location record.

        Associated links to subjects and gangs will be deleted via CASCADE.
        Events referencing this location will have their location_id set to NULL.

        Args:
            location_id: The unique identifier of the location to delete
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        self.conn.commit()

    # =========================================================================
    # EVENT OPERATIONS
    # =========================================================================

    def add_event(self, event_number: str, **kwargs) -> str:
        """
        Create a new event/incident record.

        Args:
            event_number: CAD/RMS event number or unique identifier
            **kwargs: Optional fields:
                - event_date: Date of event (YYYY-MM-DD)
                - event_type: Type of event (arrest, FI, etc.)
                - location_id: Link to locations table
                - location_text: Freetext location if not linked
                - generated_source: How event was generated
                - code_400: Disposition/400 code
                - details: Event narrative
                - case_notes: Investigator notes

        Returns:
            str: The unique 8-character ID assigned to the new event
        """
        event_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO events (id, event_number, event_date, event_type, location_id,
                               location_text, generated_source, code_400, details, case_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            event_number,
            kwargs.get('event_date', ''),
            kwargs.get('event_type', ''),
            kwargs.get('location_id', None),
            kwargs.get('location_text', ''),
            kwargs.get('generated_source', ''),
            kwargs.get('code_400', ''),
            kwargs.get('details', ''),
            kwargs.get('case_notes', '')
        ))

        self.conn.commit()
        os.makedirs(f"data/media/events/{event_id}", exist_ok=True)
        return event_id

    def get_event(self, event_id: str) -> dict:
        """
        Retrieve a single event record by ID.

        Args:
            event_id: The unique identifier of the event

        Returns:
            dict: Event data as a dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_events(self) -> list:
        """
        Retrieve all event records, ordered by date (newest first).

        Returns:
            list: List of event dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events ORDER BY event_date DESC, created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def update_event(self, event_id: str, **kwargs):
        """
        Update an existing event's information.

        Args:
            event_id: The unique identifier of the event to update
            **kwargs: Fields to update (same as add_event)
        """
        cursor = self.conn.cursor()
        allowed = ['event_number', 'event_date', 'event_type', 'location_id',
                   'location_text', 'generated_source', 'code_400', 'details', 'case_notes']

        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(event_id)
            cursor.execute(f"UPDATE events SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def delete_event(self, event_id: str):
        """
        Delete an event and all associated data.

        Cascading deletes will remove all subject/gang links and evidence.

        Args:
            event_id: The unique identifier of the event to delete
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self.conn.commit()

    # =========================================================================
    # LINKING OPERATIONS
    # =========================================================================
    # These methods create relationships between entities in the linking tables.
    # All use IntegrityError handling to silently ignore duplicate links.

    def link_subject_to_gang(self, subject_id: str, gang_id: str, **kwargs):
        """
        Create a gang membership link for a subject.

        Args:
            subject_id: The subject to link
            gang_id: The gang to link to
            **kwargs: Optional fields:
                - role: Subject's role in gang
                - status: Membership status (active/inactive)
                - notes: Additional notes

        Note:
            Silently ignores if link already exists (duplicate).
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subject_gangs (id, subject_id, gang_id, role, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (link_id, subject_id, gang_id, kwargs.get('role', ''),
                  kwargs.get('status', 'active'), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Link already exists - silently ignore duplicate
            pass

    def link_subject_to_location(self, subject_id: str, location_id: str, **kwargs):
        """
        Create a location association for a subject.

        Args:
            subject_id: The subject to link
            location_id: The location to link to
            **kwargs: Optional fields:
                - relationship: Type of association
                - is_primary_residence: 1 if primary address
                - notes: Additional notes
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subject_locations (id, subject_id, location_id, relationship,
                                               is_primary_residence, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (link_id, subject_id, location_id, kwargs.get('relationship', ''),
                  kwargs.get('is_primary_residence', 0), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def link_subject_to_event(self, subject_id: str, event_id: str, **kwargs):
        """
        Link a subject to an event with their role.

        Args:
            subject_id: The subject to link
            event_id: The event to link to
            **kwargs: Optional fields:
                - role: Subject's role (suspect, victim, witness, etc.)
                - notes: Additional notes
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subject_events (id, subject_id, event_id, role, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, subject_id, event_id, kwargs.get('role', ''), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def link_gang_to_event(self, gang_id: str, event_id: str, **kwargs):
        """
        Link a gang to an event.

        Args:
            gang_id: The gang to link
            event_id: The event to link to
            **kwargs: Optional notes field
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO gang_events (id, gang_id, event_id, notes)
                VALUES (?, ?, ?, ?)
            """, (link_id, gang_id, event_id, kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def link_gang_to_location(self, gang_id: str, location_id: str, **kwargs):
        """
        Link a gang to a location (territory/hangout).

        Args:
            gang_id: The gang to link
            location_id: The location to link to
            **kwargs: Optional fields:
                - relationship: Type (territory, hangout, trap, etc.)
                - notes: Additional notes
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO gang_locations (id, gang_id, location_id, relationship, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, gang_id, location_id, kwargs.get('relationship', ''), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def link_subjects(self, subject1_id: str, subject2_id: str, **kwargs):
        """
        Create a direct association between two subjects.

        IDs are ordered (lower first) to prevent duplicate A-B and B-A entries.

        Args:
            subject1_id: First subject
            subject2_id: Second subject
            **kwargs: Optional fields:
                - relationship: Type (associate, co-defendant, etc.)
                - notes: Additional notes
        """
        # Order IDs to prevent duplicate reverse entries
        if subject1_id > subject2_id:
            subject1_id, subject2_id = subject2_id, subject1_id

        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subject_associations (id, subject1_id, subject2_id, relationship, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, subject1_id, subject2_id, kwargs.get('relationship', 'associate'),
                  kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    # =========================================================================
    # PROFILE COMPILATION QUERIES
    # =========================================================================
    # These methods compile complete profiles by joining across multiple tables.

    def get_subject_full_profile(self, subject_id: str) -> dict:
        """
        Get complete subject profile with ALL associated data.

        This is the primary query method for displaying a subject's full
        dossier. It compiles data from all related tables including:
        - Basic subject info
        - Gang affiliations
        - Locations (residences, associations)
        - Events involvement
        - Associates (direct, shared events, same gang)
        - Social media profiles
        - Phone numbers and emails
        - Family members
        - Tattoos
        - Vehicles
        - Weapons
        - Charges
        - Case numbers
        - Intel reports

        Args:
            subject_id: The unique identifier of the subject

        Returns:
            dict: Complete subject profile with all associations,
                  or None if subject not found
        """
        subject = self.get_subject(subject_id)
        if not subject:
            return None

        cursor = self.conn.cursor()

        # Get gang affiliations with role and status
        cursor.execute("""
            SELECT g.*, sg.role, sg.status
            FROM gangs g
            JOIN subject_gangs sg ON g.id = sg.gang_id
            WHERE sg.subject_id = ?
        """, (subject_id,))
        subject['gangs'] = [dict(row) for row in cursor.fetchall()]

        # Get locations (residences and associated places)
        cursor.execute("""
            SELECT l.*, sl.relationship, sl.is_primary_residence
            FROM locations l
            JOIN subject_locations sl ON l.id = sl.location_id
            WHERE sl.subject_id = ?
        """, (subject_id,))
        subject['locations'] = [dict(row) for row in cursor.fetchall()]

        # Get events this subject was involved in
        cursor.execute("""
            SELECT e.*, se.role as subject_role
            FROM events e
            JOIN subject_events se ON e.id = se.event_id
            WHERE se.subject_id = ?
            ORDER BY e.event_date DESC
        """, (subject_id,))
        subject['events'] = [dict(row) for row in cursor.fetchall()]

        # Get direct associations (explicitly linked subjects)
        cursor.execute("""
            SELECT s.*, sa.relationship
            FROM subjects s
            JOIN subject_associations sa ON (s.id = sa.subject1_id OR s.id = sa.subject2_id)
            WHERE (sa.subject1_id = ? OR sa.subject2_id = ?) AND s.id != ?
        """, (subject_id, subject_id, subject_id))
        direct_assoc = [dict(row) for row in cursor.fetchall()]

        # Get associations through shared events
        cursor.execute("""
            SELECT DISTINCT s.*, 'shared_event' as association_type
            FROM subjects s
            JOIN subject_events se1 ON s.id = se1.subject_id
            JOIN subject_events se2 ON se1.event_id = se2.event_id
            WHERE se2.subject_id = ? AND s.id != ?
        """, (subject_id, subject_id))
        event_assoc = [dict(row) for row in cursor.fetchall()]

        # Get associations through same gang membership
        cursor.execute("""
            SELECT DISTINCT s.*, 'same_gang' as association_type
            FROM subjects s
            JOIN subject_gangs sg1 ON s.id = sg1.subject_id
            JOIN subject_gangs sg2 ON sg1.gang_id = sg2.gang_id
            WHERE sg2.subject_id = ? AND s.id != ?
        """, (subject_id, subject_id))
        gang_assoc = [dict(row) for row in cursor.fetchall()]

        # Merge and deduplicate all associations
        all_assoc = {}
        for a in direct_assoc + event_assoc + gang_assoc:
            if a['id'] not in all_assoc:
                all_assoc[a['id']] = a
        subject['associates'] = list(all_assoc.values())

        # Get social media profiles
        cursor.execute("SELECT * FROM social_profiles WHERE subject_id = ?", (subject_id,))
        subject['social_profiles'] = [dict(row) for row in cursor.fetchall()]

        # Get phone numbers
        cursor.execute("SELECT * FROM phone_numbers WHERE subject_id = ?", (subject_id,))
        subject['phone_numbers'] = [dict(row) for row in cursor.fetchall()]

        # Get emails
        cursor.execute("SELECT * FROM emails WHERE subject_id = ?", (subject_id,))
        subject['emails'] = [dict(row) for row in cursor.fetchall()]

        # Get family members
        cursor.execute("""
            SELECT fm.*, s.first_name as member_first, s.last_name as member_last
            FROM family_members fm
            LEFT JOIN subjects s ON fm.family_member_id = s.id
            WHERE fm.subject_id = ?
        """, (subject_id,))
        subject['family'] = [dict(row) for row in cursor.fetchall()]

        # Get tattoos
        subject['tattoos'] = self.get_subject_tattoos(subject_id)

        # Get vehicles
        subject['vehicles'] = self.get_subject_vehicles(subject_id)

        # Get weapons
        subject['weapons'] = self.get_subject_weapons(subject_id)

        # Get charges
        subject['charges'] = self.get_subject_charges(subject_id)

        # Get case numbers
        subject['case_numbers'] = self.get_subject_case_numbers(subject_id)

        # Get state IDs
        subject['state_ids'] = self.get_subject_state_ids(subject_id)

        # Get employment
        subject['employment'] = self.get_subject_employment(subject_id)

        # Get intel reports
        subject['intel_reports'] = self.get_subject_intel(subject_id)

        return subject

    # TODO: Write better comments

    def get_gang_full_profile(self, gang_id: str) -> dict:
        """
        Get complete gang profile with all members, locations, and events.

        Args:
            gang_id: The unique identifier of the gang

        Returns:
            dict: Complete gang profile, or None if not found
        """
        gang = self.get_gang(gang_id)
        if not gang:
            return None

        cursor = self.conn.cursor()

        # Get all members with their roles
        cursor.execute("""
            SELECT s.*, sg.role, sg.status
            FROM subjects s
            JOIN subject_gangs sg ON s.id = sg.subject_id
            WHERE sg.gang_id = ?
        """, (gang_id,))
        gang['members'] = [dict(row) for row in cursor.fetchall()]

        # Get gang locations/territories
        cursor.execute("""
            SELECT l.*, gl.relationship
            FROM locations l
            JOIN gang_locations gl ON l.id = gl.location_id
            WHERE gl.gang_id = ?
        """, (gang_id,))
        gang['locations'] = [dict(row) for row in cursor.fetchall()]

        # Get events directly involving this gang
        cursor.execute("""
            SELECT e.*
            FROM events e
            JOIN gang_events ge ON e.id = ge.event_id
            WHERE ge.gang_id = ?
            ORDER BY e.event_date DESC
        """, (gang_id,))
        gang['events'] = [dict(row) for row in cursor.fetchall()]

        # Also get events involving any members
        cursor.execute("""
            SELECT DISTINCT e.*
            FROM events e
            JOIN subject_events se ON e.id = se.event_id
            JOIN subject_gangs sg ON se.subject_id = sg.subject_id
            WHERE sg.gang_id = ?
            ORDER BY e.event_date DESC
        """, (gang_id,))
        member_events = [dict(row) for row in cursor.fetchall()]

        # Merge events (avoid duplicates)
        existing_ids = {e['id'] for e in gang['events']}
        for e in member_events:
            if e['id'] not in existing_ids:
                gang['events'].append(e)

        return gang

    def get_location_full_profile(self, location_id: str) -> dict:
        """
        Get complete location profile with all associated entities.

        Args:
            location_id: The unique identifier of the location

        Returns:
            dict: Complete location profile, or None if not found
        """
        location = self.get_location(location_id)
        if not location:
            return None

        cursor = self.conn.cursor()

        # Get subjects associated with this location
        cursor.execute("""
            SELECT s.*, sl.relationship, sl.is_primary_residence
            FROM subjects s
            JOIN subject_locations sl ON s.id = sl.subject_id
            WHERE sl.location_id = ?
        """, (location_id,))
        location['subjects'] = [dict(row) for row in cursor.fetchall()]

        # Get gangs with territory here
        cursor.execute("""
            SELECT g.*, gl.relationship
            FROM gangs g
            JOIN gang_locations gl ON g.id = gl.gang_id
            WHERE gl.location_id = ?
        """, (location_id,))
        location['gangs'] = [dict(row) for row in cursor.fetchall()]

        # Get events at this location
        cursor.execute("""
            SELECT * FROM events WHERE location_id = ?
            ORDER BY event_date DESC
        """, (location_id,))
        location['events'] = [dict(row) for row in cursor.fetchall()]

        return location

    def get_event_full_details(self, event_id: str) -> dict:
        """
        Get complete event details with all involved parties.

        Args:
            event_id: The unique identifier of the event

        Returns:
            dict: Complete event details, or None if not found
        """
        event = self.get_event(event_id)
        if not event:
            return None

        cursor = self.conn.cursor()

        # Get subjects involved
        cursor.execute("""
            SELECT s.*, se.role as event_role
            FROM subjects s
            JOIN subject_events se ON s.id = se.subject_id
            WHERE se.event_id = ?
        """, (event_id,))
        event['subjects'] = [dict(row) for row in cursor.fetchall()]

        # Get gangs involved
        cursor.execute("""
            SELECT g.*
            FROM gangs g
            JOIN gang_events ge ON g.id = ge.gang_id
            WHERE ge.event_id = ?
        """, (event_id,))
        event['gangs'] = [dict(row) for row in cursor.fetchall()]

        # Get location details if linked
        if event.get('location_id'):
            event['location'] = self.get_location(event['location_id'])

        # Get weapons
        event['weapons'] = self.get_event_weapons(event_id)

        # Get vehicles
        event['vehicles'] = self.get_event_vehicles(event_id)

        # Get evidence
        event['evidence'] = self.get_event_evidence(event_id)

        return event

    # =========================================================================
    # SOCIAL MEDIA OPERATIONS
    # =========================================================================

    def add_social_profile(self, subject_id: str, platform: str, **kwargs) -> str:
        """
        Add a social media profile for a subject.

        Args:
            subject_id: The subject who owns this profile
            platform: Platform name (Facebook, Instagram, etc.)
            **kwargs: Optional fields:
                - username: Username on platform
                - url: Direct URL to profile
                - notes: Additional notes

        Returns:
            str: ID of the new profile record
        """
        profile_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO social_profiles (id, subject_id, platform, username, url, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (profile_id, subject_id, platform, kwargs.get('username', ''),
              kwargs.get('url', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return profile_id

    def get_subject_socials(self, subject_id: str) -> list:
        """Get all social media profiles for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM social_profiles WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_social_profile(self, profile_id: str):
        """Delete a social media profile record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM social_profiles WHERE id = ?", (profile_id,))
        self.conn.commit()

    # =========================================================================
    # PHONE NUMBER OPERATIONS
    # =========================================================================

    def add_phone_number(self, subject_id: str, number: str, **kwargs) -> str:
        """
        Add a phone number for a subject.

        Args:
            subject_id: The subject who has this number
            number: Phone number
            **kwargs: Optional fields:
                - phone_type: Type (cell, home, work, burner)
                - notes: Additional notes

        Returns:
            str: ID of the new phone record
        """
        phone_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO phone_numbers (id, subject_id, number, phone_type, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (phone_id, subject_id, number, kwargs.get('phone_type', ''),
              kwargs.get('notes', '')))
        self.conn.commit()
        return phone_id

    def get_subject_phones(self, subject_id: str) -> list:
        """Get all phone numbers for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM phone_numbers WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_phone_number(self, phone_id: str):
        """Delete a phone number record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM phone_numbers WHERE id = ?", (phone_id,))
        self.conn.commit()

    # =========================================================================
    # EMAIL OPERATIONS
    # =========================================================================

    def add_email(self, subject_id: str, email: str, **kwargs) -> str:
        """
        Add an email address for a subject.

        Args:
            subject_id: The subject who has this email
            email: Email address
            **kwargs: Optional fields:
                - email_type: Type (personal, work, etc.)
                - notes: Additional notes

        Returns:
            str: ID of the new email record
        """
        email_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO emails (id, subject_id, email, email_type, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (email_id, subject_id, email, kwargs.get('email_type', ''),
              kwargs.get('notes', '')))
        self.conn.commit()
        return email_id

    def get_subject_emails(self, subject_id: str) -> list:
        """Get all email addresses for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM emails WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_email(self, email_id: str):
        """Delete an email address record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))
        self.conn.commit()

    # =========================================================================
    # FAMILY MEMBER OPERATIONS
    # =========================================================================

    def add_family_member(self, subject_id: str, relationship: str, **kwargs) -> str:
        """
        Add a family member record for a subject.

        Family members can be linked to existing subjects in the database
        or stored as just a name.

        Args:
            subject_id: The primary subject
            relationship: Relationship type (mother, father, spouse, etc.)
            **kwargs: Optional fields:
                - family_member_id: ID if family member is a subject
                - family_name: Name if not in database
                - notes: Additional notes

        Returns:
            str: ID of the new family record
        """
        family_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO family_members (id, subject_id, family_member_id, family_name, relationship, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (family_id, subject_id, kwargs.get('family_member_id'),
              kwargs.get('family_name', ''), relationship, kwargs.get('notes', '')))
        self.conn.commit()
        return family_id

    def get_subject_family(self, subject_id: str) -> list:
        """
        Get all family members for a subject.

        Joins with subjects table to get names of linked family members.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT fm.*, s.first_name as member_first, s.last_name as member_last
            FROM family_members fm
            LEFT JOIN subjects s ON fm.family_member_id = s.id
            WHERE fm.subject_id = ?
        """, (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_family_member(self, family_id: str):
        """Delete a family member record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM family_members WHERE id = ?", (family_id,))
        self.conn.commit()

    # =========================================================================
    # MEDIA OPERATIONS
    # =========================================================================

    def add_media(self, entity_type: str, entity_id: str, file_path: str, **kwargs) -> str:
        """
        Add a media file reference for any entity type.

        Args:
            entity_type: Type of entity (subject, gang, event, etc.)
            entity_id: ID of the entity
            file_path: Path to the media file
            **kwargs: Optional fields:
                - file_type: MIME type or extension
                - title: Display title
                - description: Description
                - is_pinned: 1 if this should be the bubble photo

        Returns:
            str: ID of the new media record
        """
        media_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO media (id, entity_type, entity_id, file_path, file_type, title, description, is_pinned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (media_id, entity_type, entity_id, file_path,
              kwargs.get('file_type', ''), kwargs.get('title', ''), kwargs.get('description', ''),
              kwargs.get('is_pinned', 0)))
        self.conn.commit()
        return media_id

    def set_media_pinned(self, entity_type: str, entity_id: str, media_id: str):
        """
        Set a photo as the pinned bubble photo for an entity.

        Unpins all other photos for that entity, then pins the specified one.
        """
        cursor = self.conn.cursor()
        # Unpin all photos for this entity
        cursor.execute("""
            UPDATE media SET is_pinned = 0
            WHERE entity_type = ? AND entity_id = ?
        """, (entity_type, entity_id))
        # Pin the specified photo
        cursor.execute("""
            UPDATE media SET is_pinned = 1 WHERE id = ?
        """, (media_id,))
        self.conn.commit()

    def unpin_media(self, media_id: str):
        """Unpin a specific photo."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE media SET is_pinned = 0 WHERE id = ?", (media_id,))
        self.conn.commit()

    def get_entity_media(self, entity_type: str, entity_id: str) -> list:
        """Get all media files for a specific entity."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM media WHERE entity_type = ? AND entity_id = ?
        """, (entity_type, entity_id))
        return [dict(row) for row in cursor.fetchall()]

    def get_entity_first_photo(self, entity_type: str, entity_id: str) -> str:
        """Get the bubble photo for an entity. Returns pinned photo if set, else first photo."""
        cursor = self.conn.cursor()
        # First check for pinned photo
        cursor.execute("""
            SELECT file_path FROM media
            WHERE entity_type = ? AND entity_id = ? AND is_pinned = 1
            AND (file_type = 'image' OR file_path LIKE '%.jpg'
                 OR file_path LIKE '%.jpeg' OR file_path LIKE '%.png'
                 OR file_path LIKE '%.gif')
            LIMIT 1
        """, (entity_type, entity_id))
        row = cursor.fetchone()
        if row:
            return row['file_path']

        # Fall back to first photo by creation date
        cursor.execute("""
            SELECT file_path FROM media
            WHERE entity_type = ? AND entity_id = ?
            AND (file_type = 'image' OR file_path LIKE '%.jpg'
                 OR file_path LIKE '%.jpeg' OR file_path LIKE '%.png'
                 OR file_path LIKE '%.gif')
            ORDER BY created_at ASC LIMIT 1
        """, (entity_type, entity_id))
        row = cursor.fetchone()
        return row['file_path'] if row else None

    # =========================================================================
    # GLOBAL SEARCH
    # =========================================================================

    def global_search(self, query: str) -> dict:
        """
        Search across all major entity types.

        Searches subjects, gangs, locations, and events using
        case-insensitive partial matching.

        Args:
            query: Search string

        Returns:
            dict: Dictionary with lists for each entity type:
                - subjects: Matching subjects
                - gangs: Matching gangs
                - locations: Matching locations
                - events: Matching events
        """
        results = {
            'subjects': [],
            'gangs': [],
            'locations': [],
            'events': []
        }

        search = f"%{query}%"
        cursor = self.conn.cursor()

        # Search subjects across multiple fields
        cursor.execute("""
            SELECT * FROM subjects
            WHERE first_name LIKE ? OR last_name LIKE ? OR monikers LIKE ?
                  OR ssn LIKE ? OR oln LIKE ? OR scope_id LIKE ? OR mo LIKE ?
        """, (search, search, search, search, search, search, search))
        results['subjects'] = [dict(row) for row in cursor.fetchall()]

        # Search gangs
        cursor.execute("""
            SELECT * FROM gangs WHERE name LIKE ? OR details LIKE ? OR territory LIKE ?
        """, (search, search, search))
        results['gangs'] = [dict(row) for row in cursor.fetchall()]

        # Search locations
        cursor.execute("""
            SELECT * FROM locations WHERE address LIKE ? OR description LIKE ?
        """, (search, search))
        results['locations'] = [dict(row) for row in cursor.fetchall()]

        # Search events
        cursor.execute("""
            SELECT * FROM events
            WHERE event_number LIKE ? OR location_text LIKE ? OR details LIKE ? OR case_notes LIKE ?
        """, (search, search, search, search))
        results['events'] = [dict(row) for row in cursor.fetchall()]

        return results

    # =========================================================================
    # GRAPH DATA GENERATION
    # =========================================================================

    def get_graph_data(self) -> dict:
        """
        Get all data formatted for network graph visualization.

        Generates nodes and edges for vis.js network visualization.
        Each entity becomes a node, and relationships become edges.

        Returns:
            dict: Contains:
                - nodes: List of node objects with id, label, type, data
                - edges: List of edge objects with from, to, type
        """
        nodes = []
        edges = []

        # Create nodes for all subjects
        for subject in self.get_all_subjects():
            node = {
                'id': f"subject_{subject['id']}",
                'label': f"{subject['first_name']} {subject['last_name']}",
                'type': 'subject',
                'data': subject
            }
            # Include photo - check for pinned photo first, then fallback to profile_photo
            photo = self.get_entity_first_photo('subject', subject['id'])
            if photo:
                node['photo'] = photo
            elif subject.get('profile_photo'):
                node['photo'] = subject['profile_photo']
            nodes.append(node)

        # Create nodes for all gangs
        for gang in self.get_all_gangs():
            node = {
                'id': f"gang_{gang['id']}",
                'label': gang['name'],
                'type': 'gang',
                'data': gang
            }
            # Include photo if available
            photo = self.get_entity_first_photo('gang', gang['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all locations
        for loc in self.get_all_locations():
            node = {
                'id': f"location_{loc['id']}",
                'label': loc['address'][:30],  # Truncate long addresses
                'type': 'location',
                'data': loc
            }
            photo = self.get_entity_first_photo('location', loc['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all events
        for event in self.get_all_events():
            node = {
                'id': f"event_{event['id']}",
                'label': event['event_number'] or event['id'],
                'type': 'event',
                'data': event
            }
            photo = self.get_entity_first_photo('event', event['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all vehicles
        for vehicle in self.get_all_vehicles():
            label = f"{vehicle['plate']}" if vehicle['plate'] else f"{vehicle['make']} {vehicle['model']}"
            node = {
                'id': f"vehicle_{vehicle['id']}",
                'label': label[:20],
                'type': 'vehicle',
                'data': vehicle
            }
            photo = self.get_entity_first_photo('vehicle', vehicle['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all weapons
        for weapon in self.get_all_weapons():
            label = f"{weapon['weapon_type']} {weapon['make']}"[:20] if weapon['make'] else weapon['weapon_type']
            node = {
                'id': f"weapon_{weapon['id']}",
                'label': label,
                'type': 'weapon',
                'data': weapon
            }
            photo = self.get_entity_first_photo('weapon', weapon['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all graffiti
        for graffiti in self.get_all_graffiti():
            node = {
                'id': f"graffiti_{graffiti['id']}",
                'label': f"Graffiti: {graffiti['tags'][:15]}" if graffiti['tags'] else 'Graffiti',
                'type': 'graffiti',
                'data': graffiti
            }
            photo = self.get_entity_first_photo('graffiti', graffiti['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all charges
        for charge in self.get_all_charges():
            node = {
                'id': f"charge_{charge['id']}",
                'label': f"{charge['charges_text'][:20]}" if charge['charges_text'] else 'Charge',
                'type': 'charge',
                'data': charge
            }
            photo = self.get_entity_first_photo('charge', charge['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all online accounts
        for account in self.get_all_online_accounts():
            # Short platform names for labels
            platform_short = {
                'Instagram': 'IG', 'Twitter': 'X', 'TikTok': 'TT',
                'Facebook': 'FB', 'Snapchat': 'SC', 'Telegram': 'TG',
                'YouTube': 'YT', 'Reddit': 'RD', 'Discord': 'DC'
            }.get(account['platform'], account['platform'][:3])
            username = account['username'] or 'Unknown'
            label = f"{platform_short}: @{username[:12]}"
            node = {
                'id': f"online_account_{account['id']}",
                'label': label,
                'type': 'online_account',
                'data': account
            }
            photo = self.get_entity_first_photo('online_account', account['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        # Create nodes for all DNS investigations
        for dns in self.get_all_dns_investigations():
            node = {
                'id': f"dns_{dns['id']}",
                'label': dns['domain_name'][:25],
                'type': 'dns',
                'data': dns
            }
            nodes.append(node)

        # Create nodes for all tracked phones
        for phone in self.get_all_tracked_phones():
            node = {
                'id': f"phone_{phone['id']}",
                'label': phone['phone_number'][:14],
                'type': 'phone',
                'data': phone
            }
            nodes.append(node)

        # Create nodes for all intel reports
        for intel in self.get_all_intel_reports():
            label = f"Intel: {intel.get('source_type', '')[:10]}" if intel.get('source_type') else 'Intel Report'
            node = {
                'id': f"intel_{intel['id']}",
                'label': label,
                'type': 'event',  # Use event group color
                'data': intel
            }
            nodes.append(node)

        # Create nodes for all posts
        for post in self.get_all_account_posts():
            title = post.get('title', '').strip() if post.get('title') else ''
            if title:
                label = f"Post: {title[:15]}"
            else:
                label = f"Post: {post.get('post_type', 'Post')}"
            node = {
                'id': f"post_{post['id']}",
                'label': label,
                'type': 'post',
                'data': post
            }
            photo = self.get_entity_first_photo('post', post['id'])
            if photo:
                node['photo'] = photo
            nodes.append(node)

        cursor = self.conn.cursor()

        # Create edges for all relationships

        # Subject-Gang membership edges
        cursor.execute("SELECT * FROM subject_gangs")
        for row in cursor.fetchall():
            edges.append({
                'from': f"subject_{row['subject_id']}",
                'to': f"gang_{row['gang_id']}",
                'type': 'member_of'
            })

        # Subject-Event involvement edges
        cursor.execute("SELECT * FROM subject_events")
        for row in cursor.fetchall():
            edges.append({
                'from': f"subject_{row['subject_id']}",
                'to': f"event_{row['event_id']}",
                'type': 'involved_in'
            })

        # Subject-Location association edges
        cursor.execute("SELECT * FROM subject_locations")
        for row in cursor.fetchall():
            edges.append({
                'from': f"subject_{row['subject_id']}",
                'to': f"location_{row['location_id']}",
                'type': 'resides_at' if row['is_primary_residence'] else 'associated_with'
            })

        # Subject-Vehicle edges
        cursor.execute("SELECT * FROM subject_vehicles")
        for row in cursor.fetchall():
            edges.append({
                'from': f"subject_{row['subject_id']}",
                'to': f"vehicle_{row['vehicle_id']}",
                'type': 'drives'
            })

        # Subject-Weapon edges
        cursor.execute("SELECT * FROM subject_weapons")
        for row in cursor.fetchall():
            edges.append({
                'from': f"subject_{row['subject_id']}",
                'to': f"weapon_{row['weapon_id']}",
                'type': 'possesses'
            })

        # Gang-Event edges
        cursor.execute("SELECT * FROM gang_events")
        for row in cursor.fetchall():
            edges.append({
                'from': f"gang_{row['gang_id']}",
                'to': f"event_{row['event_id']}",
                'type': 'involved_in'
            })

        # Gang-Location territory edges
        cursor.execute("SELECT * FROM gang_locations")
        for row in cursor.fetchall():
            edges.append({
                'from': f"gang_{row['gang_id']}",
                'to': f"location_{row['location_id']}",
                'type': 'territory'
            })

        # Event-Vehicle edges
        cursor.execute("SELECT * FROM event_vehicles")
        for row in cursor.fetchall():
            edges.append({
                'from': f"event_{row['event_id']}",
                'to': f"vehicle_{row['vehicle_id']}",
                'type': 'involved_vehicle'
            })

        # Event-Weapon edges
        cursor.execute("SELECT * FROM event_weapons")
        for row in cursor.fetchall():
            edges.append({
                'from': f"event_{row['event_id']}",
                'to': f"weapon_{row['weapon_id']}",
                'type': 'involved_weapon'
            })

        # Subject-Subject association edges
        cursor.execute("SELECT * FROM subject_associations")
        for row in cursor.fetchall():
            edges.append({
                'from': f"subject_{row['subject1_id']}",
                'to': f"subject_{row['subject2_id']}",
                'type': 'associate'
            })

        # Charge edges
        cursor.execute("SELECT * FROM charges")
        for row in cursor.fetchall():
            # Charge to subject (who was charged)
            edges.append({
                'from': f"charge_{row['id']}",
                'to': f"subject_{row['subject_id']}",
                'type': 'charged'
            })
            # Charge to event if linked
            if row['event_id']:
                edges.append({
                    'from': f"charge_{row['id']}",
                    'to': f"event_{row['event_id']}",
                    'type': 'from_event'
                })
            # Charge to gang if gang-related
            if row['gang_id']:
                edges.append({
                    'from': f"charge_{row['id']}",
                    'to': f"gang_{row['gang_id']}",
                    'type': 'gang_related'
                })

        # Graffiti edges
        cursor.execute("SELECT * FROM graffiti")
        for row in cursor.fetchall():
            if row['location_id']:
                edges.append({
                    'from': f"graffiti_{row['id']}",
                    'to': f"location_{row['location_id']}",
                    'type': 'at_location'
                })
            if row['gang_id']:
                edges.append({
                    'from': f"graffiti_{row['id']}",
                    'to': f"gang_{row['gang_id']}",
                    'type': 'gang_tag'
                })

        # Online Account edges (account to subject)
        cursor.execute("SELECT * FROM online_accounts WHERE subject_id IS NOT NULL")
        for row in cursor.fetchall():
            edges.append({
                'from': f"online_account_{row['id']}",
                'to': f"subject_{row['subject_id']}",
                'type': 'belongs_to'
            })

        # DNS Investigation edges (DNS to subject and/or account)
        cursor.execute("SELECT * FROM dns_investigations")
        for row in cursor.fetchall():
            if row['subject_id']:
                edges.append({
                    'from': f"dns_{row['id']}",
                    'to': f"subject_{row['subject_id']}",
                    'type': 'linked_to'
                })
            if row['account_id']:
                edges.append({
                    'from': f"dns_{row['id']}",
                    'to': f"online_account_{row['account_id']}",
                    'type': 'domain_for'
                })

        # Account association edges (account to account)
        cursor.execute("SELECT * FROM account_associations")
        for row in cursor.fetchall():
            edges.append({
                'from': f"online_account_{row['account1_id']}",
                'to': f"online_account_{row['account2_id']}",
                'type': 'associated_account'
            })

        # Tracked phone edges (phone to subject and/or account)
        cursor.execute("SELECT * FROM tracked_phones")
        for row in cursor.fetchall():
            if row['subject_id']:
                edges.append({
                    'from': f"phone_{row['id']}",
                    'to': f"subject_{row['subject_id']}",
                    'type': 'belongs_to'
                })
            if row['account_id']:
                edges.append({
                    'from': f"phone_{row['id']}",
                    'to': f"online_account_{row['account_id']}",
                    'type': 'linked_to'
                })

        # Account-Vehicle edges
        cursor.execute("SELECT * FROM account_vehicles")
        for row in cursor.fetchall():
            edges.append({
                'from': f"online_account_{row['account_id']}",
                'to': f"vehicle_{row['vehicle_id']}",
                'type': 'linked_vehicle'
            })

        # Post edges (post to account)
        cursor.execute("SELECT id, account_id FROM account_posts WHERE account_id IS NOT NULL")
        for row in cursor.fetchall():
            edges.append({
                'from': f"post_{row['id']}",
                'to': f"online_account_{row['account_id']}",
                'type': 'posted_on'
            })

        # Intel report edges (link to subjects, gangs, locations, events)
        cursor.execute("SELECT * FROM intel_reports")
        for row in cursor.fetchall():
            if row['subject_id']:
                edges.append({
                    'from': f"intel_{row['id']}",
                    'to': f"subject_{row['subject_id']}",
                    'type': 'intel_subject'
                })
            if row['gang_id']:
                edges.append({
                    'from': f"intel_{row['id']}",
                    'to': f"gang_{row['gang_id']}",
                    'type': 'intel_gang'
                })
            if row['location_id']:
                edges.append({
                    'from': f"intel_{row['id']}",
                    'to': f"location_{row['location_id']}",
                    'type': 'intel_location'
                })
            if row['event_id']:
                edges.append({
                    'from': f"intel_{row['id']}",
                    'to': f"event_{row['event_id']}",
                    'type': 'intel_event'
                })

        # Charge-to-location edges
        cursor.execute("SELECT id, location_id FROM charges WHERE location_id IS NOT NULL")
        for row in cursor.fetchall():
            edges.append({
                'from': f"charge_{row['id']}",
                'to': f"location_{row['location_id']}",
                'type': 'charge_location'
            })

        # Event-to-location edges (from FK)
        cursor.execute("SELECT id, location_id FROM events WHERE location_id IS NOT NULL")
        for row in cursor.fetchall():
            edges.append({
                'from': f"event_{row['id']}",
                'to': f"location_{row['location_id']}",
                'type': 'event_location'
            })

        # Universal Entity Links edges (spider web connections)
        cursor.execute("SELECT * FROM entity_links")
        for row in cursor.fetchall():
            edges.append({
                'from': f"{row['source_type']}_{row['source_id']}",
                'to': f"{row['target_type']}_{row['target_id']}",
                'type': 'universal_link'
            })

        # Position nodes so separate webs start spread apart
        import math

        # Build adjacency list
        adjacency = {}
        node_ids = {n['id'] for n in nodes}
        for edge in edges:
            if edge['from'] in node_ids and edge['to'] in node_ids:
                if edge['from'] not in adjacency:
                    adjacency[edge['from']] = set()
                if edge['to'] not in adjacency:
                    adjacency[edge['to']] = set()
                adjacency[edge['from']].add(edge['to'])
                adjacency[edge['to']].add(edge['from'])

        # Find connected components using BFS
        visited = set()
        components = []

        for node in nodes:
            node_id = node['id']
            if node_id in visited:
                continue

            # BFS to find this component
            component = []
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                if current in adjacency:
                    for neighbor in adjacency[current]:
                        if neighbor not in visited:
                            queue.append(neighbor)

            components.append(component)

        # Position each component in a grid, spread apart
        node_positions = {}
        component_spacing = 800  # Distance between component centers
        cols = max(1, int(math.ceil(math.sqrt(len(components)))))

        for comp_idx, component in enumerate(components):
            # Component center position (grid layout)
            comp_row = comp_idx // cols
            comp_col = comp_idx % cols
            center_x = comp_col * component_spacing
            center_y = comp_row * component_spacing

            if len(component) == 1:
                # Single node - just place at center
                node_positions[component[0]] = (center_x, center_y)
            else:
                # Radial layout within component
                # Pick a central node (first one, or most connected)
                central_node = component[0]
                max_connections = 0
                for node_id in component:
                    conn_count = len(adjacency.get(node_id, []))
                    if conn_count > max_connections:
                        max_connections = conn_count
                        central_node = node_id

                # BFS from central node for distances
                distances = {central_node: 0}
                queue = [(central_node, 0)]
                while queue:
                    current, dist = queue.pop(0)
                    if current in adjacency:
                        for neighbor in adjacency[current]:
                            if neighbor in component and neighbor not in distances:
                                distances[neighbor] = dist + 1
                                queue.append((neighbor, dist + 1))

                # Group by distance
                by_distance = {}
                for node_id, dist in distances.items():
                    if dist not in by_distance:
                        by_distance[dist] = []
                    by_distance[dist].append(node_id)

                # Assign positions
                radius_step = 200
                for dist, node_ids_at_dist in by_distance.items():
                    if dist == 0:
                        node_positions[node_ids_at_dist[0]] = (center_x, center_y)
                    else:
                        radius = dist * radius_step
                        count = len(node_ids_at_dist)
                        for i, nid in enumerate(node_ids_at_dist):
                            angle = (2 * math.pi * i / count) + (dist * 0.3)
                            x = center_x + radius * math.cos(angle)
                            y = center_y + radius * math.sin(angle)
                            node_positions[nid] = (x, y)

        # Add positions to nodes
        for node in nodes:
            if node['id'] in node_positions:
                node['x'] = node_positions[node['id']][0]
                node['y'] = node_positions[node['id']][1]

        return {'nodes': nodes, 'edges': edges}

    def get_focused_graph_data(self, entity_type: str, entity_id: str) -> dict:
        """
        Get graph data for the entire connected web containing the selected entity.

        Uses BFS traversal to find ALL nodes reachable from the selected entity
        through any chain of connections. Assigns radial positions so nodes
        start spread out based on their distance from the selected entity.

        Args:
            entity_type: Type of the selected entity (subject, vehicle, etc.)
            entity_id: ID of the selected entity

        Returns:
            dict: Contains all nodes and edges in the connected web with positions
        """
        import math

        # Get full graph data first
        full_data = self.get_graph_data()

        # Build the selected node ID
        selected_node_id = f"{entity_type}_{entity_id}"

        # Build adjacency list for fast traversal
        adjacency = {}
        for edge in full_data['edges']:
            if edge['from'] not in adjacency:
                adjacency[edge['from']] = set()
            if edge['to'] not in adjacency:
                adjacency[edge['to']] = set()
            adjacency[edge['from']].add(edge['to'])
            adjacency[edge['to']].add(edge['from'])

        # BFS to find all connected nodes with their distance from selected
        connected_ids = {}  # node_id -> distance from selected
        queue = [(selected_node_id, 0)]

        while queue:
            current, distance = queue.pop(0)
            if current in connected_ids:
                continue
            connected_ids[current] = distance
            # Add all neighbors to queue
            if current in adjacency:
                for neighbor in adjacency[current]:
                    if neighbor not in connected_ids:
                        queue.append((neighbor, distance + 1))

        # Group nodes by distance for radial layout
        nodes_by_distance = {}
        for node_id, dist in connected_ids.items():
            if dist not in nodes_by_distance:
                nodes_by_distance[dist] = []
            nodes_by_distance[dist].append(node_id)

        # Assign positions: selected node at center, others in rings
        node_positions = {}
        radius_step = 250  # Distance between rings

        for distance, node_ids in nodes_by_distance.items():
            if distance == 0:
                # Center node
                node_positions[node_ids[0]] = (0, 0)
            else:
                # Spread nodes in a circle at this distance
                radius = distance * radius_step
                count = len(node_ids)
                for i, node_id in enumerate(node_ids):
                    angle = (2 * math.pi * i / count) + (distance * 0.5)  # Offset each ring
                    x = radius * math.cos(angle)
                    y = radius * math.sin(angle)
                    node_positions[node_id] = (x, y)

        # Filter and add positions to nodes
        filtered_nodes = []
        for n in full_data['nodes']:
            if n['id'] in connected_ids:
                node_copy = n.copy()
                if n['id'] in node_positions:
                    node_copy['x'] = node_positions[n['id']][0]
                    node_copy['y'] = node_positions[n['id']][1]
                filtered_nodes.append(node_copy)

        # Filter edges to only include edges between connected nodes
        filtered_edges = [
            e for e in full_data['edges']
            if e['from'] in connected_ids and e['to'] in connected_ids
        ]

        return {'nodes': filtered_nodes, 'edges': filtered_edges}

    # =========================================================================
    # TATTOO OPERATIONS
    # =========================================================================

    def add_tattoo(self, subject_id: str, description: str, **kwargs) -> str:
        """
        Add a tattoo record for a subject.

        Args:
            subject_id: The subject with the tattoo
            description: Description of the tattoo
            **kwargs: Optional fields:
                - body_location: Where on body
                - is_gang_affiliated: 1 if gang-related
                - photo_path: Path to tattoo photo
                - notes: Additional notes

        Returns:
            str: ID of the new tattoo record
        """
        tattoo_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tattoos (id, subject_id, description, body_location, is_gang_affiliated, photo_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tattoo_id, subject_id, description, kwargs.get('body_location', ''),
              kwargs.get('is_gang_affiliated', 0), kwargs.get('photo_path', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return tattoo_id

    def get_subject_tattoos(self, subject_id: str) -> list:
        """Get all tattoos for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tattoos WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_tattoo(self, tattoo_id: str):
        """Delete a tattoo record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tattoos WHERE id = ?", (tattoo_id,))
        self.conn.commit()

    # =========================================================================
    # VEHICLE OPERATIONS
    # =========================================================================

    def add_vehicle(self, **kwargs) -> str:
        """
        Add a new vehicle record.

        Args:
            **kwargs: Vehicle fields:
                - plate: License plate number
                - state: Registration state
                - make: Vehicle make
                - model: Vehicle model
                - year: Model year
                - color: Vehicle color
                - vin: VIN
                - notes: Additional notes

        Returns:
            str: ID of the new vehicle record
        """
        vehicle_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO vehicles (id, plate, state, make, model, year, color, vin, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (vehicle_id, kwargs.get('plate', ''), kwargs.get('state', ''),
              kwargs.get('make', ''), kwargs.get('model', ''), kwargs.get('year', ''),
              kwargs.get('color', ''), kwargs.get('vin', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return vehicle_id

    def get_vehicle(self, vehicle_id: str) -> dict:
        """Get a vehicle by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_vehicles(self) -> list:
        """Get all vehicles, ordered by plate."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM vehicles ORDER BY plate")
        return [dict(row) for row in cursor.fetchall()]

    def find_existing_vehicle(self, plate: str = None, vin: str = None) -> str | None:
        """
        Find an existing vehicle by plate or VIN.

        Args:
            plate: License plate to search for
            vin: VIN to search for

        Returns:
            str | None: ID of found vehicle, or None
        """
        cursor = self.conn.cursor()

        # Check by plate first
        if plate and plate.strip():
            cursor.execute("SELECT id FROM vehicles WHERE UPPER(plate) = UPPER(?)", (plate.strip(),))
            row = cursor.fetchone()
            if row:
                return row['id']

        # Check by VIN
        if vin and vin.strip():
            cursor.execute("SELECT id FROM vehicles WHERE UPPER(vin) = UPPER(?)", (vin.strip(),))
            row = cursor.fetchone()
            if row:
                return row['id']

        return None

    def find_or_create_vehicle(self, plate: str, **kwargs) -> str:
        """Find vehicle by plate/VIN or create new one."""
        existing_id = self.find_existing_vehicle(plate=plate, vin=kwargs.get('vin'))
        if existing_id:
            return existing_id
        return self.add_vehicle(plate=plate, **kwargs)

    def delete_vehicle(self, vehicle_id: str):
        """Delete a vehicle record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        self.conn.commit()

    def link_subject_to_vehicle(self, subject_id: str, vehicle_id: str, **kwargs):
        """Link a subject to a vehicle."""
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subject_vehicles (id, subject_id, vehicle_id, relationship, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, subject_id, vehicle_id, kwargs.get('relationship', ''), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def is_subject_linked_to_vehicle(self, subject_id: str, vehicle_id: str) -> bool:
        """Check if a subject is already linked to a vehicle."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM subject_vehicles WHERE subject_id = ? AND vehicle_id = ?",
            (subject_id, vehicle_id)
        )
        return cursor.fetchone() is not None

    def is_event_linked_to_vehicle(self, event_id: str, vehicle_id: str) -> bool:
        """Check if an event is already linked to a vehicle."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM event_vehicles WHERE event_id = ? AND vehicle_id = ?",
            (event_id, vehicle_id)
        )
        return cursor.fetchone() is not None

    def link_event_to_vehicle(self, event_id: str, vehicle_id: str, **kwargs):
        """Link an event to a vehicle."""
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO event_vehicles (id, event_id, vehicle_id, notes)
                VALUES (?, ?, ?, ?)
            """, (link_id, event_id, vehicle_id, kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_subject_vehicles(self, subject_id: str) -> list:
        """Get all vehicles for a subject with relationship info."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT v.*, sv.relationship
            FROM vehicles v
            JOIN subject_vehicles sv ON v.id = sv.vehicle_id
            WHERE sv.subject_id = ?
        """, (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_event_vehicles(self, event_id: str) -> list:
        """Get all vehicles involved in an event."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT v.*, ev.notes as event_notes
            FROM vehicles v
            JOIN event_vehicles ev ON v.id = ev.vehicle_id
            WHERE ev.event_id = ?
        """, (event_id,))
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # WEAPON OPERATIONS
    # =========================================================================

    def add_weapon(self, **kwargs) -> str:
        """
        Add a new weapon record.

        Args:
            **kwargs: Weapon fields:
                - weapon_type: Type (handgun, rifle, etc.)
                - make: Manufacturer
                - model: Model name
                - caliber: Caliber/gauge
                - serial_number: Serial number
                - notes: Additional notes

        Returns:
            str: ID of the new weapon record
        """
        weapon_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO weapons (id, weapon_type, make, model, caliber, serial_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (weapon_id, kwargs.get('weapon_type', ''), kwargs.get('make', ''),
              kwargs.get('model', ''), kwargs.get('caliber', ''),
              kwargs.get('serial_number', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return weapon_id

    def get_weapon(self, weapon_id: str) -> dict:
        """Get a weapon by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM weapons WHERE id = ?", (weapon_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_weapons(self) -> list:
        """Get all weapons, ordered by type and make."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM weapons ORDER BY weapon_type, make")
        return [dict(row) for row in cursor.fetchall()]

    def find_or_create_weapon(self, serial_number: str = None, **kwargs) -> str:
        """Find weapon by serial number or create new one."""
        if serial_number:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM weapons WHERE serial_number = ?", (serial_number,))
            row = cursor.fetchone()
            if row:
                return row['id']
        return self.add_weapon(serial_number=serial_number, **kwargs)

    def delete_weapon(self, weapon_id: str):
        """Delete a weapon record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM weapons WHERE id = ?", (weapon_id,))
        self.conn.commit()

    def link_subject_to_weapon(self, subject_id: str, weapon_id: str, **kwargs):
        """Link a subject to a weapon."""
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subject_weapons (id, subject_id, weapon_id, relationship, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, subject_id, weapon_id, kwargs.get('relationship', ''), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def link_event_to_weapon(self, event_id: str, weapon_id: str, **kwargs):
        """Link an event to a weapon."""
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO event_weapons (id, event_id, weapon_id, disposition, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, event_id, weapon_id, kwargs.get('disposition', ''), kwargs.get('notes', '')))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_subject_weapons(self, subject_id: str) -> list:
        """Get all weapons for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT w.*, sw.relationship
            FROM weapons w
            JOIN subject_weapons sw ON w.id = sw.weapon_id
            WHERE sw.subject_id = ?
        """, (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_event_weapons(self, event_id: str) -> list:
        """Get all weapons involved in an event."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT w.*, ew.disposition, ew.notes as event_notes
            FROM weapons w
            JOIN event_weapons ew ON w.id = ew.weapon_id
            WHERE ew.event_id = ?
        """, (event_id,))
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # EVIDENCE OPERATIONS
    # =========================================================================

    def add_evidence(self, event_id: str, description: str, **kwargs) -> str:
        """
        Add evidence to an event.

        Args:
            event_id: The event this evidence relates to
            description: Description of the evidence
            **kwargs: Optional fields:
                - evidence_type: Type (physical, digital, etc.)
                - location_found: Where found
                - disposition: What happened to it
                - photo_path: Photo of evidence
                - notes: Additional notes

        Returns:
            str: ID of the new evidence record
        """
        evidence_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO evidence (id, event_id, description, evidence_type, location_found, disposition, photo_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (evidence_id, event_id, description, kwargs.get('evidence_type', ''),
              kwargs.get('location_found', ''), kwargs.get('disposition', ''),
              kwargs.get('photo_path', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return evidence_id

    def get_event_evidence(self, event_id: str) -> list:
        """Get all evidence for an event."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM evidence WHERE event_id = ?", (event_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_evidence(self, evidence_id: str):
        """Delete an evidence record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
        self.conn.commit()

    # =========================================================================
    # CHARGES OPERATIONS
    # =========================================================================

    def add_charge(self, subject_id: str, charges_text: str, **kwargs) -> str:
        """
        Add a criminal charge record.

        Args:
            subject_id: Who was charged
            charges_text: Charge description/statute
            **kwargs: Optional fields:
                - event_id: Related event
                - charge_date: Date of charge
                - location_id: Where charge occurred
                - location_text: Freetext location
                - court_case_number: Court case number
                - court_url: URL to court records
                - gang_id: Related gang
                - details: Charge details
                - notes: Additional notes

        Returns:
            str: ID of the new charge record
        """
        charge_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO charges (id, subject_id, event_id, charges_text, charge_date, location_id,
                                location_text, court_case_number, court_url, gang_id, details, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (charge_id, subject_id, kwargs.get('event_id'), charges_text,
              kwargs.get('charge_date', ''), kwargs.get('location_id'),
              kwargs.get('location_text', ''), kwargs.get('court_case_number', ''),
              kwargs.get('court_url', ''), kwargs.get('gang_id'),
              kwargs.get('details', ''), kwargs.get('notes', '')))
        self.conn.commit()
        os.makedirs(f"data/media/charges/{charge_id}", exist_ok=True)
        return charge_id

    def get_charge(self, charge_id: str) -> dict:
        """Get a charge by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM charges WHERE id = ?", (charge_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_charges(self) -> list:
        """Get all charges with subject names."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, s.first_name, s.last_name
            FROM charges c
            LEFT JOIN subjects s ON c.subject_id = s.id
            ORDER BY c.charge_date DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_subject_charges(self, subject_id: str) -> list:
        """Get all charges for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM charges WHERE subject_id = ? ORDER BY charge_date DESC", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_charge(self, charge_id: str):
        """Delete a charge record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM charges WHERE id = ?", (charge_id,))
        self.conn.commit()

    def add_charge_affiliate(self, charge_id: str, subject_id: str, role: str = 'co-defendant'):
        """Add a co-defendant to a charge."""
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO charge_affiliates (id, charge_id, subject_id, role)
                VALUES (?, ?, ?, ?)
            """, (link_id, charge_id, subject_id, role))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_charge_affiliates(self, charge_id: str) -> list:
        """Get all co-defendants for a charge."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.*, ca.role
            FROM subjects s
            JOIN charge_affiliates ca ON s.id = ca.subject_id
            WHERE ca.charge_id = ?
        """, (charge_id,))
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # GRAFFITI OPERATIONS
    # =========================================================================

    def add_graffiti(self, **kwargs) -> str:
        """
        Add a graffiti sighting record.

        Args:
            **kwargs: Graffiti fields:
                - location_id: Link to locations table
                - location_text: Freetext location
                - tags: What was written/drawn
                - gang_id: Attributed gang
                - monikers: Monikers in graffiti
                - sector_beat: Police sector/beat
                - area_command: Area command
                - date_observed: When observed
                - notes: Additional notes

        Returns:
            str: ID of the new graffiti record
        """
        graffiti_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO graffiti (id, location_id, location_text, tags, gang_id, monikers,
                                 sector_beat, area_command, date_observed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (graffiti_id, kwargs.get('location_id'), kwargs.get('location_text', ''),
              kwargs.get('tags', ''), kwargs.get('gang_id'), kwargs.get('monikers', ''),
              kwargs.get('sector_beat', ''), kwargs.get('area_command', ''),
              kwargs.get('date_observed', ''), kwargs.get('notes', '')))
        self.conn.commit()
        os.makedirs(f"data/media/graffiti/{graffiti_id}", exist_ok=True)
        return graffiti_id

    def get_graffiti(self, graffiti_id: str) -> dict:
        """Get a graffiti record by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM graffiti WHERE id = ?", (graffiti_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_graffiti(self) -> list:
        """Get all graffiti with gang names."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT gr.*, g.name as gang_name
            FROM graffiti gr
            LEFT JOIN gangs g ON gr.gang_id = g.id
            ORDER BY gr.date_observed DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def delete_graffiti(self, graffiti_id: str):
        """Delete a graffiti record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM graffiti WHERE id = ?", (graffiti_id,))
        self.conn.commit()

    # =========================================================================
    # INTEL REPORT OPERATIONS
    # =========================================================================

    def add_intel_report(self, source_type: str, details: str, **kwargs) -> str:
        """
        Add an intelligence report.

        Args:
            source_type: Source type (CI, social media, etc.)
            details: Intelligence content
            **kwargs: Optional fields:
                - report_date: Date of report
                - reliability: Source reliability rating
                - subject_id: Related subject
                - gang_id: Related gang
                - location_id: Related location
                - event_id: Related event
                - notes: Additional notes

        Returns:
            str: ID of the new intel report
        """
        report_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO intel_reports (id, report_date, source_type, reliability, details,
                                       subject_id, gang_id, location_id, event_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (report_id, kwargs.get('report_date', datetime.now().strftime('%Y-%m-%d')),
              source_type, kwargs.get('reliability', ''), details,
              kwargs.get('subject_id'), kwargs.get('gang_id'),
              kwargs.get('location_id'), kwargs.get('event_id'), kwargs.get('notes', '')))
        self.conn.commit()
        return report_id

    def get_intel_report(self, report_id: str) -> dict:
        """Get an intel report by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM intel_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_intel_reports(self) -> list:
        """Get all intel reports, newest first."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM intel_reports ORDER BY report_date DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_subject_intel(self, subject_id: str) -> list:
        """Get all intel reports for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM intel_reports WHERE subject_id = ? ORDER BY report_date DESC", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_intel_report(self, report_id: str):
        """Delete an intel report."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM intel_reports WHERE id = ?", (report_id,))
        self.conn.commit()

    # =========================================================================
    # CASE NUMBER OPERATIONS
    # =========================================================================

    def add_case_number(self, subject_id: str, case_number: str, **kwargs) -> str:
        """
        Add a court case number for a subject.

        Args:
            subject_id: The subject
            case_number: Court case number
            **kwargs: Optional fields:
                - case_type: Type (criminal, civil, etc.)
                - court: Which court
                - status: Case status
                - url: URL to case info
                - notes: Additional notes

        Returns:
            str: ID of the new case number record
        """
        case_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO case_numbers (id, subject_id, case_number, case_type, court, status, url, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (case_id, subject_id, case_number, kwargs.get('case_type', ''),
              kwargs.get('court', ''), kwargs.get('status', ''),
              kwargs.get('url', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return case_id

    def get_subject_case_numbers(self, subject_id: str) -> list:
        """Get all case numbers for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM case_numbers WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_case_number(self, case_id: str):
        """Delete a case number record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM case_numbers WHERE id = ?", (case_id,))
        self.conn.commit()

    # =========================================================================
    # STATE ID OPERATIONS
    # =========================================================================

    def add_state_id(self, subject_id: str, id_number: str, **kwargs) -> str:
        """Add a government ID for a subject (State ID, RISSAFE, etc.)."""
        sid = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO state_ids (id, subject_id, id_number, id_type, state, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sid, subject_id, id_number, kwargs.get('id_type', ''),
              kwargs.get('state', ''), kwargs.get('notes', '')))
        self.conn.commit()
        return sid

    def get_subject_state_ids(self, subject_id: str) -> list:
        """Get all government IDs for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM state_ids WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_state_id(self, state_id_record: str):
        """Delete a state ID record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM state_ids WHERE id = ?", (state_id_record,))
        self.conn.commit()

    # =========================================================================
    # EMPLOYMENT OPERATIONS
    # =========================================================================

    def add_employment(self, subject_id: str, employer: str, **kwargs) -> str:
        """Add an employment/business affiliation for a subject."""
        emp_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO employment (id, subject_id, employer, position, address, phone,
                                    start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (emp_id, subject_id, employer, kwargs.get('position', ''),
              kwargs.get('address', ''), kwargs.get('phone', ''),
              kwargs.get('start_date', ''), kwargs.get('end_date', ''),
              kwargs.get('notes', '')))
        self.conn.commit()
        return emp_id

    def get_subject_employment(self, subject_id: str) -> list:
        """Get all employment records for a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM employment WHERE subject_id = ?", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_employment(self, emp_id: str):
        """Delete an employment record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employment WHERE id = ?", (emp_id,))
        self.conn.commit()

    # =========================================================================
    # CHECKLIST OPERATIONS
    # =========================================================================

    def _insert_default_checklist_items(self):
        """
        Insert the default OSINT checklist items.

        These are the standard sources to check for each subject.
        Users can add custom items and deactivate defaults.

        Categories include:
        - LE Databases: Law enforcement databases
        - Financial: Payment apps and services
        - Social Media: Social media platforms
        - Messaging: Messaging apps
        - Records: Public records
        - People Search: People search engines
        - Email: Email investigation tools
        - Username: Username search tools
        - Vehicle: Vehicle lookup tools
        - Image: Reverse image search
        """
        defaults = [
            # LE Databases - Law enforcement systems (no URLs - internal systems)
            ('LE Databases', 'SCOPE', '', 'NV State Records', 1),
            ('LE Databases', 'DMV', '', 'Driver/Vehicle Records', 2),
            ('LE Databases', 'Triple I', '', 'Interstate Identification Index', 3),
            ('LE Databases', 'NCJIS', '', 'Nevada Criminal Justice Info System', 4),
            ('LE Databases', 'NCIC', '', 'National Crime Information Center', 5),
            ('LE Databases', 'LEADS', '', 'Law Enforcement Automated Data', 6),
            ('LE Databases', 'RISSAFE', '', 'Regional Intel Sharing Systems', 7),
            ('LE Databases', 'NLETS', '', 'National LE Telecommunications', 8),

            # Financial - Payment services
            ('Financial', 'CashApp', 'https://cash.app/', 'Search by phone/cashtag', 10),
            ('Financial', 'Venmo', 'https://venmo.com/', 'Search by phone/username', 11),
            ('Financial', 'Zelle', '', 'Check through bank apps', 12),
            ('Financial', 'PayPal', 'https://paypal.com/', 'Search by email', 13),

            # Social Media - Social platforms
            ('Social Media', 'Facebook', 'https://facebook.com/search/', 'Profile search', 20),
            ('Social Media', 'Instagram', 'https://instagram.com/', 'Profile search', 21),
            ('Social Media', 'TikTok', 'https://tiktok.com/', 'Profile search', 22),
            ('Social Media', 'Snapchat', 'https://snapchat.com/', 'Add by username', 23),
            ('Social Media', 'Twitter/X', 'https://x.com/search', 'Profile search', 24),
            ('Social Media', 'LinkedIn', 'https://linkedin.com/search/', 'Professional network', 25),
            ('Social Media', 'YouTube', 'https://youtube.com/results', 'Video search', 26),
            ('Social Media', 'Reddit', 'https://reddit.com/search/', 'Reddit search', 27),

            # Messaging - Communication apps
            ('Messaging', 'WhatsApp', '', 'Check by phone number', 30),
            ('Messaging', 'Telegram', 'https://t.me/', 'Search by username', 31),
            ('Messaging', 'Signal', '', 'Check by phone number', 32),
            ('Messaging', 'Discord', 'https://discord.com/', 'Gaming/community platform', 33),

            # Records - Public records
            ('Records', 'Clark County Assessor', 'https://maps.clarkcountynv.gov/assessor/AssessorParcelSearch/', 'NV property records', 40),
            ('Records', 'Clark County Recorder', 'https://recorder.clarkcountynv.gov/AcclaimWeb/search/SearchTypeDocType', 'NV recorded documents', 41),
            ('Records', 'NV Court Search', 'https://www.clarkcountycourts.us/Anonymous/default.aspx', 'Clark County courts', 42),
            ('Records', 'Federal Court PACER', 'https://pacer.uscourts.gov/', 'Federal court records', 43),
            ('Records', 'NV SOS Business Search', 'https://esos.nv.gov/EntitySearch/OnlineEntitySearch', 'Business entity search', 44),
            ('Records', 'Inmate Search - NDOC', 'https://ofdsearch.doc.nv.gov/', 'NV prison inmates', 45),
            ('Records', 'Federal BOP Inmate Locator', 'https://www.bop.gov/inmateloc/', 'Federal inmates', 46),

            # People Search - People search engines
            ('People Search', 'TruePeopleSearch', 'https://truepeoplesearch.com/', 'Free people search', 50),
            ('People Search', 'FastPeopleSearch', 'https://fastpeoplesearch.com/', 'Free people search', 51),
            ('People Search', 'IDCrawl', 'https://idcrawl.com/', 'Username/name search', 52),
            ('People Search', 'That\'s Them', 'https://thatsthem.com/', 'Free people search', 53),
            ('People Search', 'Webmii', 'https://webmii.com/', 'Web presence search', 54),
            ('People Search', 'Pipl', 'https://pipl.com/', 'Identity search (paid)', 55),
            ('People Search', 'Spokeo', 'https://spokeo.com/', 'People search', 56),
            ('People Search', 'Unmask', 'https://unmask.com/', 'Phone/email lookup', 57),
            ('People Search', 'CyberBackgroundChecks', 'https://cyberbackgroundchecks.com/', 'Background check', 58),
            ('People Search', 'Nuwber', 'https://nuwber.com/', 'People search engine', 59),
            ('People Search', 'BeenVerified', 'https://beenverified.com/', 'Background checks', 60),
            ('People Search', 'Intelius', 'https://intelius.com/', 'People search', 61),
            ('People Search', 'WhitePages', 'https://whitepages.com/', 'Phone/address lookup', 62),
            ('People Search', 'ZabaSearch', 'https://zabasearch.com/', 'Free people search', 63),
            ('People Search', 'PeekYou', 'https://peekyou.com/', 'Social media aggregator', 64),
            ('People Search', 'USSearch', 'https://ussearch.com/', 'People finder', 65),
            ('People Search', 'Radaris', 'https://radaris.com/', 'Public records search', 66),

            # Email - Email investigation
            ('Email', 'Have I Been Pwned', 'https://haveibeenpwned.com/', 'Breach checker', 200),
            ('Email', 'Hunter.io', 'https://hunter.io/', 'Email lookup', 201),
            ('Email', 'EmailRep', 'https://emailrep.io/', 'Email reputation', 202),
            ('Email', 'Epieos', 'https://epieos.com/', 'Email OSINT tool', 203),

            # Username - Username search
            ('Username', 'Namechk', 'https://namechk.com/', 'Username availability', 210),
            ('Username', 'WhatsMyName', 'https://whatsmyname.app/', 'Username search', 211),
            ('Username', 'Sherlock (GitHub)', 'https://github.com/sherlock-project/sherlock', 'Username hunt tool', 212),
            ('Username', 'Instant Username', 'https://instantusername.com/', 'Username availability', 213),
            ('Username', 'KnowEm', 'https://knowem.com/', 'Username/brand search', 214),

            # Phone - Phone lookup
            ('Phone', 'NumLookup', 'https://numlookup.com/', 'Free phone lookup', 220),
            ('Phone', 'Carrier Lookup', 'https://freecarrierlookup.com/', 'Carrier identification', 221),
            ('Phone', 'CallerID Test', 'https://calleridtest.com/', 'Caller ID lookup', 222),
            ('Phone', 'SpyDialer', 'https://spydialer.com/', 'Reverse phone lookup', 223),
            ('Phone', 'ThatsThem Phone', 'https://thatsthem.com/reverse-phone-lookup', 'Reverse phone', 224),
            ('Phone', 'USPhoneBook', 'https://usphonebook.com/', 'Phone directory', 225),

            # Vehicle - Vehicle lookup
            ('Vehicle', 'NHTSA VIN Decoder', 'https://vpic.nhtsa.dot.gov/decoder/', 'Official VIN decoder', 80),
            ('Vehicle', 'NICB VINCheck', 'https://www.nicb.org/vincheck', 'Theft/salvage check', 81),
            ('Vehicle', 'VINDecoder.net', 'https://vindecoder.net/', 'Free VIN lookup', 82),
            ('Vehicle', 'NHTSA Recalls', 'https://www.nhtsa.gov/recalls', 'Vehicle recall search', 83),
            ('Vehicle', 'VehicleHistory', 'https://vehiclehistory.com/', 'Free vehicle history', 84),
            ('Vehicle', 'iSeeCars VIN', 'https://www.iseecars.com/vin', 'VIN check tool', 85),

            # Image - Reverse image search
            ('Image', 'Google Images', 'https://images.google.com/', 'Reverse image search', 90),
            ('Image', 'TinEye', 'https://tineye.com/', 'Reverse image search', 91),
            ('Image', 'PimEyes', 'https://pimeyes.com/', 'Face search engine', 92),
            ('Image', 'Yandex Images', 'https://yandex.com/images/', 'Russian image search', 93),
            ('Image', 'Bing Visual Search', 'https://www.bing.com/visualsearch', 'MS reverse image', 94),
            ('Image', 'FaceCheck.ID', 'https://facecheck.id/', 'Face search tool', 95),
            ('Image', 'Social Catfish', 'https://socialcatfish.com/', 'Image/identity search', 96),

            # Domain/IP - Website investigation
            ('Domain/IP', 'Whois Lookup', 'https://whois.domaintools.com/', 'Domain registration', 100),
            ('Domain/IP', 'ViewDNS', 'https://viewdns.info/', 'DNS tools', 101),
            ('Domain/IP', 'BuiltWith', 'https://builtwith.com/', 'Technology lookup', 102),
            ('Domain/IP', 'Wayback Machine', 'https://web.archive.org/', 'Website history', 103),
            ('Domain/IP', 'URLScan', 'https://urlscan.io/', 'URL analysis', 104),
            ('Domain/IP', 'Shodan', 'https://shodan.io/', 'IoT/device search', 105),
            ('Domain/IP', 'DNSDumpster', 'https://dnsdumpster.com/', 'DNS recon & research', 106),
            ('Domain/IP', 'SecurityTrails', 'https://securitytrails.com/', 'Historical DNS data', 107),
            ('Domain/IP', 'crt.sh', 'https://crt.sh/', 'Certificate transparency logs', 108),
            ('Domain/IP', 'VirusTotal', 'https://virustotal.com/', 'URL/domain scanning', 109),

            # Dark Web / Underground
            ('Dark Web', 'IntelX', 'https://intelx.io/', 'Darkweb/breach search', 130),
            ('Dark Web', 'Dehashed', 'https://dehashed.com/', 'Breach database search', 131),
            ('Dark Web', 'LeakCheck', 'https://leakcheck.io/', 'Leak database lookup', 132),

            # Geolocation - Location tools
            ('Geolocation', 'Google Maps', 'https://maps.google.com/', 'Mapping/street view', 110),
            ('Geolocation', 'Google Earth', 'https://earth.google.com/web/', 'Satellite imagery', 111),
            ('Geolocation', 'Bing Maps', 'https://www.bing.com/maps', 'Bird\'s eye view', 112),
            ('Geolocation', 'SunCalc', 'https://suncalc.org/', 'Sun position calculator', 113),

            # Misc OSINT Tools
            ('OSINT Tools', 'OSINT Framework', 'https://osintframework.com/', 'OSINT resource directory', 120),
            ('OSINT Tools', 'IntelTechniques', 'https://inteltechniques.com/tools/', 'OSINT tools collection', 121),
            ('OSINT Tools', 'Maltego', 'https://maltego.com/', 'Link analysis tool', 122),
        ]

        cursor = self.conn.cursor()
        for cat, name, url, desc, order in defaults:
            item_id = str(uuid.uuid4())[:8]
            cursor.execute("""
                INSERT INTO checklist_items (id, category, name, url, description, sort_order, is_default)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (item_id, cat, name, url, desc, order))
        self.conn.commit()

    def get_all_checklist_items(self) -> list:
        """Get all active checklist items."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM checklist_items WHERE is_active = 1 ORDER BY sort_order, category, name
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_checklist_by_category(self) -> dict:
        """
        Get checklist items grouped by category.

        Returns:
            dict: Category names as keys, lists of items as values
        """
        items = self.get_all_checklist_items()
        grouped = {}
        for item in items:
            cat = item['category']
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(item)
        return grouped

    def add_checklist_item(self, category: str, name: str, **kwargs) -> str:
        """
        Add a custom checklist item.

        Custom items have is_default=0 and can be fully deleted.

        Args:
            category: Category name
            name: Item name
            **kwargs: Optional fields:
                - url: URL to open
                - description: How to use
                - sort_order: Display order

        Returns:
            str: ID of the new checklist item
        """
        item_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO checklist_items (id, category, name, url, description, sort_order, is_default)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (item_id, category, name, kwargs.get('url', ''),
              kwargs.get('description', ''), kwargs.get('sort_order', 100)))
        self.conn.commit()
        return item_id

    def update_checklist_item(self, item_id: str, **kwargs):
        """Update a checklist item."""
        cursor = self.conn.cursor()
        allowed = ['category', 'name', 'url', 'description', 'sort_order', 'is_active']
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        if updates:
            values.append(item_id)
            cursor.execute(f"UPDATE checklist_items SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def delete_checklist_item(self, item_id: str):
        """
        Delete a checklist item.

        Default items are deactivated rather than deleted.
        Custom items are fully deleted.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_default FROM checklist_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row and row['is_default']:
            # Deactivate default items instead of deleting
            cursor.execute("UPDATE checklist_items SET is_active = 0 WHERE id = ?", (item_id,))
        else:
            # Fully delete custom items
            cursor.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
        self.conn.commit()

    # =========================================================================
    # CHECKLIST PROGRESS OPERATIONS
    # =========================================================================

    def get_subject_checklist_progress(self, subject_id: str) -> dict:
        """
        Get checklist completion status for a subject.

        Returns:
            dict: Checklist item IDs as keys, progress records as values
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT cp.*, ci.category, ci.name, ci.url, ci.description
            FROM checklist_progress cp
            JOIN checklist_items ci ON cp.checklist_item_id = ci.id
            WHERE cp.subject_id = ?
        """, (subject_id,))
        progress = {}
        for row in cursor.fetchall():
            progress[row['checklist_item_id']] = dict(row)
        return progress

    def update_checklist_progress(self, subject_id: str, item_id: str, completed: bool, notes: str = ''):
        """
        Update checklist progress for a subject.

        Uses INSERT ... ON CONFLICT to create or update the progress record.

        Args:
            subject_id: The subject
            item_id: The checklist item
            completed: Whether completed
            notes: Results or notes
        """
        progress_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        completed_date = datetime.now().strftime('%Y-%m-%d') if completed else None

        cursor.execute("""
            INSERT INTO checklist_progress (id, subject_id, checklist_item_id, completed, completed_date, result_notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject_id, checklist_item_id) DO UPDATE SET
                completed = excluded.completed,
                completed_date = excluded.completed_date,
                result_notes = excluded.result_notes
        """, (progress_id, subject_id, item_id, 1 if completed else 0, completed_date, notes))
        self.conn.commit()

    # =========================================================================
    # ONLINE ACCOUNTS OPERATIONS
    # =========================================================================

    def add_online_account(self, platform: str, **kwargs) -> str:
        """
        Create a new online account record.

        Args:
            platform: The platform (Twitter, Instagram, TikTok, etc.)
            **kwargs: Optional fields:
                - platform_account_id: Permanent platform ID
                - username: Current username
                - display_name: Display name
                - profile_url: URL to profile
                - account_type: Personal, Business, Bot, Unknown
                - status: Active, Suspended, Deleted, Private
                - subject_id: Link to subject
                - notes: Additional notes

        Returns:
            str: ID of the new account record
        """
        account_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO online_accounts (id, platform, platform_account_id, username, display_name,
                                         profile_url, account_type, status, subject_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            platform,
            kwargs.get('platform_account_id', ''),
            kwargs.get('username', ''),
            kwargs.get('display_name', ''),
            kwargs.get('profile_url', ''),
            kwargs.get('account_type', 'Unknown'),
            kwargs.get('status', 'Active'),
            kwargs.get('subject_id'),
            kwargs.get('notes', '')
        ))
        self.conn.commit()
        os.makedirs(f"data/media/online_accounts/{account_id}", exist_ok=True)
        return account_id

    def get_online_account(self, account_id: str) -> dict:
        """Get an online account by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM online_accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_online_accounts(self) -> list:
        """Get all online accounts, ordered by platform and username."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM online_accounts ORDER BY platform, username")
        return [dict(row) for row in cursor.fetchall()]

    def get_subject_online_accounts(self, subject_id: str) -> list:
        """Get all online accounts linked to a subject."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM online_accounts WHERE subject_id = ? ORDER BY platform", (subject_id,))
        return [dict(row) for row in cursor.fetchall()]

    def update_online_account(self, account_id: str, **kwargs):
        """Update an online account."""
        cursor = self.conn.cursor()
        allowed = ['platform', 'platform_account_id', 'username', 'display_name',
                   'profile_url', 'account_type', 'status', 'subject_id', 'notes']
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(account_id)
            cursor.execute(f"UPDATE online_accounts SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def delete_online_account(self, account_id: str):
        """Delete an online account and its posts."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM online_accounts WHERE id = ?", (account_id,))
        self.conn.commit()
        # Remove account's media directory
        media_path = f"data/media/online_accounts/{account_id}"
        if os.path.exists(media_path):
            shutil.rmtree(media_path)

    def find_existing_online_account(self, platform: str, username: str = None,
                                      platform_account_id: str = None, profile_url: str = None) -> str | None:
        """
        Find an existing online account by platform + username, platform_account_id, or profile_url.

        Args:
            platform: The platform (Twitter, Instagram, etc.)
            username: Username to search for
            platform_account_id: Platform's permanent ID
            profile_url: Profile URL

        Returns:
            str | None: ID of found account, or None
        """
        cursor = self.conn.cursor()

        # Check by platform + platform_account_id first (most reliable)
        if platform_account_id and platform_account_id.strip():
            cursor.execute("""
                SELECT id FROM online_accounts
                WHERE LOWER(platform) = LOWER(?) AND platform_account_id = ?
            """, (platform.strip(), platform_account_id.strip()))
            row = cursor.fetchone()
            if row:
                return row['id']

        # Check by platform + username
        if username and username.strip():
            cursor.execute("""
                SELECT id FROM online_accounts
                WHERE LOWER(platform) = LOWER(?) AND LOWER(username) = LOWER(?)
            """, (platform.strip(), username.strip()))
            row = cursor.fetchone()
            if row:
                return row['id']

        # Check by profile_url
        if profile_url and profile_url.strip():
            cursor.execute("""
                SELECT id FROM online_accounts
                WHERE LOWER(profile_url) = LOWER(?)
            """, (profile_url.strip(),))
            row = cursor.fetchone()
            if row:
                return row['id']

        return None

    def link_account_to_subject(self, account_id: str, subject_id: str):
        """Link an online account to a subject."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE online_accounts SET subject_id = ?, updated_at = ? WHERE id = ?
        """, (subject_id, datetime.now().isoformat(), account_id))
        self.conn.commit()

    # =========================================================================
    # ACCOUNT POSTS OPERATIONS
    # =========================================================================

    def add_account_post(self, account_id: str, **kwargs) -> str:
        """
        Add a post/activity record for an online account.

        Args:
            account_id: The online account this post belongs to
            **kwargs: Optional fields:
                - title: User-defined title for identification
                - post_date: When post was made
                - captured_date: When we captured it
                - post_url: Direct link
                - post_type: Post, Comment, Story, Reel, Message, Listing
                - content_text: Text content
                - activity_type: Drug Sale, Weapon Sale, Threat, Gang Activity, Other
                - notes: Additional notes

        Returns:
            str: ID of the new post record
        """
        post_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO account_posts (id, account_id, title, post_date, captured_date, post_url,
                                       post_type, content_text, activity_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_id,
            account_id,
            kwargs.get('title', ''),
            kwargs.get('post_date', ''),
            kwargs.get('captured_date', datetime.now().strftime('%Y-%m-%d')),
            kwargs.get('post_url', ''),
            kwargs.get('post_type', 'Post'),
            kwargs.get('content_text', ''),
            kwargs.get('activity_type', ''),
            kwargs.get('notes', '')
        ))
        self.conn.commit()
        os.makedirs(f"data/media/account_posts/{post_id}", exist_ok=True)
        return post_id

    def get_account_posts(self, account_id: str) -> list:
        """Get all posts for an online account."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM account_posts WHERE account_id = ? ORDER BY post_date DESC
        """, (account_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_account_posts(self) -> list:
        """Get all account posts across all accounts."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM account_posts ORDER BY post_date DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_account_post(self, post_id: str) -> dict:
        """Get a single account post by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM account_posts WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_account_post(self, post_id: str, **kwargs):
        """Update an existing account post."""
        cursor = self.conn.cursor()
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in ['account_id', 'title', 'post_date', 'captured_date', 'post_url', 'post_type',
                       'content_text', 'activity_type', 'notes']:
                updates.append(f"{key} = ?")
                values.append(value)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(post_id)
            cursor.execute(f"UPDATE account_posts SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def delete_account_post(self, post_id: str):
        """Delete an account post."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM account_posts WHERE id = ?", (post_id,))
        self.conn.commit()
        # Remove post's media directory
        media_path = f"data/media/account_posts/{post_id}"
        if os.path.exists(media_path):
            shutil.rmtree(media_path)

    # =========================================================================
    # DNS INVESTIGATIONS OPERATIONS
    # =========================================================================

    def add_dns_investigation(self, domain_name: str, **kwargs) -> str:
        """
        Create a new DNS investigation record.

        Args:
            domain_name: The domain being investigated
            **kwargs: Optional fields for DNS records and WHOIS data

        Returns:
            str: ID of the new investigation record
        """
        dns_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO dns_investigations (id, domain_name, investigation_date, a_records, aaaa_records,
                                            mx_records, txt_records, cname_records, ns_records,
                                            registrar, registrant_name, registrant_email,
                                            registration_date, expiration_date, hosting_provider,
                                            ip_addresses, subject_id, account_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dns_id,
            domain_name,
            kwargs.get('investigation_date', datetime.now().strftime('%Y-%m-%d')),
            kwargs.get('a_records', ''),
            kwargs.get('aaaa_records', ''),
            kwargs.get('mx_records', ''),
            kwargs.get('txt_records', ''),
            kwargs.get('cname_records', ''),
            kwargs.get('ns_records', ''),
            kwargs.get('registrar', ''),
            kwargs.get('registrant_name', ''),
            kwargs.get('registrant_email', ''),
            kwargs.get('registration_date', ''),
            kwargs.get('expiration_date', ''),
            kwargs.get('hosting_provider', ''),
            kwargs.get('ip_addresses', ''),
            kwargs.get('subject_id'),
            kwargs.get('account_id'),
            kwargs.get('notes', '')
        ))
        self.conn.commit()
        return dns_id

    def get_dns_investigation(self, dns_id: str) -> dict:
        """Get a DNS investigation by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM dns_investigations WHERE id = ?", (dns_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_dns_investigations(self) -> list:
        """Get all DNS investigations, newest first."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM dns_investigations ORDER BY investigation_date DESC")
        return [dict(row) for row in cursor.fetchall()]

    def update_dns_investigation(self, dns_id: str, **kwargs):
        """Update a DNS investigation."""
        cursor = self.conn.cursor()
        allowed = ['domain_name', 'investigation_date', 'a_records', 'aaaa_records',
                   'mx_records', 'txt_records', 'cname_records', 'ns_records',
                   'registrar', 'registrant_name', 'registrant_email',
                   'registration_date', 'expiration_date', 'hosting_provider',
                   'ip_addresses', 'subject_id', 'account_id', 'notes']
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(dns_id)
            cursor.execute(f"UPDATE dns_investigations SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def delete_dns_investigation(self, dns_id: str):
        """Delete a DNS investigation."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM dns_investigations WHERE id = ?", (dns_id,))
        self.conn.commit()

    # =========================================================================
    # CUSTOM LINKS OPERATIONS
    # =========================================================================

    def add_custom_link(self, entity_type: str, entity_id: str, title: str, **kwargs) -> str:
        """
        Add a custom link to any entity.

        Args:
            entity_type: Type of entity (subject, event, gang, account, dns, etc.)
            entity_id: ID of the entity
            title: Short title for the link
            **kwargs: Optional fields:
                - link_type: Type of link (Evidence, Related Case, Informant Tip, etc.)
                - description: Detailed description
                - url: Optional URL
                - notes: Additional notes

        Returns:
            str: ID of the new custom link
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO custom_links (id, link_type, title, description, url, entity_type, entity_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            link_id,
            kwargs.get('link_type', ''),
            title,
            kwargs.get('description', ''),
            kwargs.get('url', ''),
            entity_type,
            entity_id,
            kwargs.get('notes', '')
        ))
        self.conn.commit()
        return link_id

    def get_entity_custom_links(self, entity_type: str, entity_id: str) -> list:
        """Get all custom links for a specific entity."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM custom_links WHERE entity_type = ? AND entity_id = ?
            ORDER BY created_at DESC
        """, (entity_type, entity_id))
        return [dict(row) for row in cursor.fetchall()]

    def delete_custom_link(self, link_id: str):
        """Delete a custom link."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM custom_links WHERE id = ?", (link_id,))
        self.conn.commit()

    # =========================================================================
    # ACCOUNT ASSOCIATIONS OPERATIONS
    # =========================================================================

    def add_account_association(self, account1_id: str, account2_id: str, **kwargs) -> str:
        """
        Link two online accounts together.

        Args:
            account1_id: First account ID
            account2_id: Second account ID
            **kwargs: Optional fields:
                - association_type: Type of link (Promoting same content, Same person, etc.)
                - evidence: Description of why they're linked
                - confidence: Low, Medium, High, Confirmed
                - discovered_date: When the link was discovered
                - notes: Additional notes

        Returns:
            str: ID of the new association
        """
        # Ensure consistent ordering (smaller ID first) to prevent duplicates
        if account1_id > account2_id:
            account1_id, account2_id = account2_id, account1_id

        assoc_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO account_associations (id, account1_id, account2_id, association_type,
                                                   evidence, confidence, discovered_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assoc_id,
                account1_id,
                account2_id,
                kwargs.get('association_type', ''),
                kwargs.get('evidence', ''),
                kwargs.get('confidence', 'Medium'),
                kwargs.get('discovered_date', datetime.now().strftime('%Y-%m-%d')),
                kwargs.get('notes', '')
            ))
            self.conn.commit()
            return assoc_id
        except Exception:
            # Association already exists
            return None

    def get_account_associations(self, account_id: str) -> list:
        """Get all accounts associated with this account."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT aa.*,
                   CASE WHEN aa.account1_id = ? THEN oa2.id ELSE oa1.id END as linked_account_id,
                   CASE WHEN aa.account1_id = ? THEN oa2.platform ELSE oa1.platform END as linked_platform,
                   CASE WHEN aa.account1_id = ? THEN oa2.username ELSE oa1.username END as linked_username
            FROM account_associations aa
            JOIN online_accounts oa1 ON aa.account1_id = oa1.id
            JOIN online_accounts oa2 ON aa.account2_id = oa2.id
            WHERE aa.account1_id = ? OR aa.account2_id = ?
        """, (account_id, account_id, account_id, account_id, account_id))
        return [dict(row) for row in cursor.fetchall()]

    def delete_account_association(self, assoc_id: str):
        """Delete an account association."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM account_associations WHERE id = ?", (assoc_id,))
        self.conn.commit()

    # =========================================================================
    # ACCOUNT-VEHICLE LINKING
    # =========================================================================

    def link_account_to_vehicle(self, account_id: str, vehicle_id: str, **kwargs) -> str:
        """
        Link an online account to a vehicle.

        Args:
            account_id: The online account ID
            vehicle_id: The vehicle ID
            **kwargs: Optional fields:
                - relationship: How they're linked (Driven in video, For sale, etc.)
                - evidence: Where/how the link was discovered
                - notes: Additional notes

        Returns:
            str: ID of the new link, or None if already exists
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO account_vehicles (id, account_id, vehicle_id, relationship, evidence, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                link_id,
                account_id,
                vehicle_id,
                kwargs.get('relationship', ''),
                kwargs.get('evidence', ''),
                kwargs.get('notes', '')
            ))
            self.conn.commit()
            return link_id
        except Exception:
            return None

    def get_account_vehicles(self, account_id: str) -> list:
        """Get all vehicles linked to this account."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT av.*, v.plate, v.make, v.model, v.color, v.year
            FROM account_vehicles av
            JOIN vehicles v ON av.vehicle_id = v.id
            WHERE av.account_id = ?
        """, (account_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_vehicle_accounts(self, vehicle_id: str) -> list:
        """Get all online accounts linked to this vehicle."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT av.*, oa.platform, oa.username, oa.display_name
            FROM account_vehicles av
            JOIN online_accounts oa ON av.account_id = oa.id
            WHERE av.vehicle_id = ?
        """, (vehicle_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_account_vehicle_link(self, link_id: str):
        """Delete an account-vehicle link."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM account_vehicles WHERE id = ?", (link_id,))
        self.conn.commit()

    def get_account_network(self, account_id: str, depth: int = 2) -> dict:
        """
        Get the network of associated accounts up to a certain depth.

        Returns a dict with 'accounts' (list of account dicts) and
        'associations' (list of association dicts) for graph visualization.
        """
        visited = set()
        accounts = []
        associations = []
        queue = [(account_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)

            account = self.get_online_account(current_id)
            if account:
                accounts.append(account)

            if current_depth < depth:
                assocs = self.get_account_associations(current_id)
                for assoc in assocs:
                    associations.append(assoc)
                    linked_id = assoc['linked_account_id']
                    if linked_id not in visited:
                        queue.append((linked_id, current_depth + 1))

        return {'accounts': accounts, 'associations': associations}

    # =========================================================================
    # TRACKED PHONES OPERATIONS
    # =========================================================================

    def add_tracked_phone(self, phone_number: str, **kwargs) -> str:
        """
        Create a new tracked phone number record.

        Args:
            phone_number: The phone number to track
            **kwargs: Optional fields:
                - phone_type: Cell, Landline, VoIP, Burner, Unknown
                - carrier: Carrier name
                - carrier_type: Wireless, Landline, VoIP
                - location_area: City/State
                - status: Active, Disconnected, Unknown
                - registered_name: Name from lookup
                - first_seen_date: When first encountered
                - last_seen_date: Most recent activity
                - subject_id: Link to subject
                - account_id: Link to online account
                - notes: Additional notes

        Returns:
            str: ID of the new phone record
        """
        phone_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tracked_phones (id, phone_number, phone_type, carrier, carrier_type,
                                        location_area, status, registered_name, first_seen_date,
                                        last_seen_date, subject_id, account_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            phone_id,
            phone_number,
            kwargs.get('phone_type', 'Unknown'),
            kwargs.get('carrier', ''),
            kwargs.get('carrier_type', ''),
            kwargs.get('location_area', ''),
            kwargs.get('status', 'Active'),
            kwargs.get('registered_name', ''),
            kwargs.get('first_seen_date', ''),
            kwargs.get('last_seen_date', ''),
            kwargs.get('subject_id'),
            kwargs.get('account_id'),
            kwargs.get('notes', '')
        ))
        self.conn.commit()
        return phone_id

    def get_tracked_phone(self, phone_id: str) -> dict:
        """Get a tracked phone by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracked_phones WHERE id = ?", (phone_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_tracked_phones(self) -> list:
        """Get all tracked phones, ordered by phone number."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracked_phones ORDER BY phone_number")
        return [dict(row) for row in cursor.fetchall()]

    def update_tracked_phone(self, phone_id: str, **kwargs):
        """Update a tracked phone."""
        cursor = self.conn.cursor()
        allowed = ['phone_number', 'phone_type', 'carrier', 'carrier_type', 'location_area',
                   'status', 'registered_name', 'first_seen_date', 'last_seen_date',
                   'subject_id', 'account_id', 'notes']
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(phone_id)
            cursor.execute(f"UPDATE tracked_phones SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()

    def find_existing_tracked_phone(self, phone_number: str) -> str | None:
        """
        Find an existing tracked phone by phone number.

        Uses normalized comparison (strips non-digits for matching).

        Args:
            phone_number: Phone number to search for

        Returns:
            str | None: ID of found phone, or None
        """
        import re
        cursor = self.conn.cursor()

        # Normalize: remove all non-digit characters for comparison
        normalized = re.sub(r'\D', '', phone_number) if phone_number else ''

        if normalized:
            # Get all phones and compare normalized versions
            cursor.execute("SELECT id, phone_number FROM tracked_phones")
            for row in cursor.fetchall():
                existing_normalized = re.sub(r'\D', '', row['phone_number'] or '')
                if existing_normalized == normalized:
                    return row['id']

        return None

    def delete_tracked_phone(self, phone_id: str):
        """Delete a tracked phone."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tracked_phones WHERE id = ?", (phone_id,))
        self.conn.commit()

    def link_phone_to_subject(self, phone_id: str, subject_id: str):
        """Link a tracked phone to a subject."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tracked_phones SET subject_id = ?, updated_at = ? WHERE id = ?
        """, (subject_id, datetime.now().isoformat(), phone_id))
        self.conn.commit()

    def link_phone_to_account(self, phone_id: str, account_id: str):
        """Link a tracked phone to an online account."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tracked_phones SET account_id = ?, updated_at = ? WHERE id = ?
        """, (account_id, datetime.now().isoformat(), phone_id))
        self.conn.commit()

    # =========================================================================
    # UNIVERSAL ENTITY LINKS OPERATIONS
    # =========================================================================
    # Methods for linking any entity to any other entity (spider web connections)

    def add_entity_link(self, source_type: str, source_id: str, target_type: str, target_id: str, **kwargs) -> str:
        """
        Create a universal link between any two entities.

        Args:
            source_type: Type of source entity (subject, vehicle, online_account, etc.)
            source_id: ID of the source entity
            target_type: Type of target entity
            target_id: ID of the target entity
            **kwargs: Optional fields (relationship, direction, evidence, confidence, notes)

        Returns:
            Link ID if successful, None if duplicate or error
        """
        link_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO entity_links (id, source_type, source_id, target_type, target_id,
                                          relationship, direction, evidence, confidence, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                link_id,
                source_type,
                source_id,
                target_type,
                target_id,
                kwargs.get('relationship', ''),
                kwargs.get('direction', 'both'),
                kwargs.get('evidence', ''),
                kwargs.get('confidence', 'Medium'),
                kwargs.get('notes', '')
            ))
            self.conn.commit()
            return link_id
        except sqlite3.IntegrityError:
            return None  # Duplicate link
        except Exception:
            return None

    def get_entity_links(self, entity_type: str, entity_id: str) -> list:
        """
        Get all links for an entity (both as source and as target).

        Returns list of dicts with link info and resolved entity names.
        """
        cursor = self.conn.cursor()
        links = []

        # Links where this entity is the source
        cursor.execute("""
            SELECT id, source_type, source_id, target_type, target_id,
                   relationship, direction, evidence, confidence, notes, created_at
            FROM entity_links
            WHERE source_type = ? AND source_id = ?
        """, (entity_type, entity_id))

        for row in cursor.fetchall():
            link = {
                'id': row[0],
                'source_type': row[1],
                'source_id': row[2],
                'target_type': row[3],
                'target_id': row[4],
                'relationship': row[5],
                'direction': row[6],
                'evidence': row[7],
                'confidence': row[8],
                'notes': row[9],
                'created_at': row[10],
                'link_direction': 'outgoing',
                'linked_type': row[3],
                'linked_id': row[4],
                'linked_name': self._get_entity_display_name(row[3], row[4])
            }
            links.append(link)

        # Links where this entity is the target (and direction allows reverse visibility)
        cursor.execute("""
            SELECT id, source_type, source_id, target_type, target_id,
                   relationship, direction, evidence, confidence, notes, created_at
            FROM entity_links
            WHERE target_type = ? AND target_id = ? AND direction IN ('both', 'reverse')
        """, (entity_type, entity_id))

        for row in cursor.fetchall():
            link = {
                'id': row[0],
                'source_type': row[1],
                'source_id': row[2],
                'target_type': row[3],
                'target_id': row[4],
                'relationship': row[5],
                'direction': row[6],
                'evidence': row[7],
                'confidence': row[8],
                'notes': row[9],
                'created_at': row[10],
                'link_direction': 'incoming',
                'linked_type': row[1],
                'linked_id': row[2],
                'linked_name': self._get_entity_display_name(row[1], row[2])
            }
            links.append(link)

        return links

    def _get_entity_display_name(self, entity_type: str, entity_id: str) -> str:
        """Get a display name for any entity type."""
        try:
            if entity_type == 'subject':
                s = self.get_subject(entity_id)
                return f"{s['first_name']} {s['last_name']}" if s else 'Unknown Subject'
            elif entity_type == 'vehicle':
                v = self.get_vehicle(entity_id)
                return f"{v.get('plate', 'No Plate')} - {v.get('make', '')} {v.get('model', '')}" if v else 'Unknown Vehicle'
            elif entity_type == 'online_account':
                a = self.get_online_account(entity_id)
                if a:
                    return f"@{a['username']}" if a.get('username') else f"{a.get('platform', 'Account')}"
                return 'Unknown Account'
            elif entity_type == 'event':
                e = self.get_event(entity_id)
                return e.get('event_number', 'Unknown Event') if e else 'Unknown Event'
            elif entity_type == 'gang':
                g = self.get_gang(entity_id)
                return g.get('name', 'Unknown Gang') if g else 'Unknown Gang'
            elif entity_type == 'location':
                l = self.get_location(entity_id)
                return l.get('address', 'Unknown Location') if l else 'Unknown Location'
            elif entity_type == 'weapon':
                w = self.get_weapon(entity_id)
                return f"{w.get('weapon_type', '')} - {w.get('make', '')} {w.get('model', '')}" if w else 'Unknown Weapon'
            elif entity_type == 'phone':
                p = self.get_tracked_phone(entity_id)
                return p.get('phone_number', 'Unknown Phone') if p else 'Unknown Phone'
            elif entity_type == 'dns':
                d = self.get_dns_investigation(entity_id)
                return d.get('domain_name', 'Unknown Domain') if d else 'Unknown Domain'
            elif entity_type == 'post':
                # Account posts - use title if available
                cursor = self.conn.cursor()
                cursor.execute("SELECT title, content_text, post_type FROM account_posts WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                if row:
                    # Prefer title, then content preview, then post type
                    if row[0] and row[0].strip():
                        return row[0].strip()
                    text = row[1][:30] + '...' if row[1] and len(row[1]) > 30 else (row[1] or row[2] or 'Post')
                    return text
                return 'Unknown Post'
            else:
                return f"{entity_type}: {entity_id[:8]}"
        except Exception:
            return f"{entity_type}: {entity_id[:8]}"

    def delete_entity_link(self, link_id: str) -> bool:
        """Delete a universal entity link."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM entity_links WHERE id = ?", (link_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    def get_all_entity_links(self) -> list:
        """Get all entity links for graph visualization."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, source_type, source_id, target_type, target_id,
                   relationship, direction, evidence, confidence
            FROM entity_links
        """)
        return [
            {
                'id': row[0],
                'source_type': row[1],
                'source_id': row[2],
                'target_type': row[3],
                'target_id': row[4],
                'relationship': row[5],
                'direction': row[6],
                'evidence': row[7],
                'confidence': row[8]
            }
            for row in cursor.fetchall()
        ]

    # =========================================================================
    # ADDITIONAL UPDATE METHODS
    # =========================================================================

    def update_vehicle(self, vehicle_id: str, **kwargs):
        """Update a vehicle record."""
        allowed = ['plate', 'state', 'make', 'model', 'year', 'color', 'vin', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE vehicles SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [vehicle_id])
        self.conn.commit()

    def update_weapon(self, weapon_id: str, **kwargs):
        """Update a weapon record."""
        allowed = ['weapon_type', 'make', 'model', 'caliber', 'serial_number', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE weapons SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [weapon_id])
        self.conn.commit()

    def update_charge(self, charge_id: str, **kwargs):
        """Update a charge record."""
        allowed = ['subject_id', 'event_id', 'charges_text', 'charge_date', 'location_id',
                    'location_text', 'court_case_number', 'court_url', 'gang_id', 'details', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE charges SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [charge_id])
        self.conn.commit()

    def update_graffiti(self, graffiti_id: str, **kwargs):
        """Update a graffiti record."""
        allowed = ['location_id', 'location_text', 'tags', 'gang_id', 'monikers',
                    'sector_beat', 'area_command', 'date_observed', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE graffiti SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [graffiti_id])
        self.conn.commit()

    def update_intel_report(self, report_id: str, **kwargs):
        """Update an intel report record."""
        allowed = ['report_date', 'source_type', 'reliability', 'details',
                    'subject_id', 'gang_id', 'location_id', 'event_id', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE intel_reports SET {set_clause} WHERE id = ?",
                       list(updates.values()) + [report_id])
        self.conn.commit()

    # =========================================================================
    # DELETE MEDIA
    # =========================================================================

    def delete_media(self, media_id: str):
        """Delete a media record by ID."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM media WHERE id = ?", (media_id,))
        self.conn.commit()

    # =========================================================================
    # UNLINK METHODS
    # =========================================================================

    def unlink_subject_from_gang(self, subject_id: str, gang_id: str):
        """Remove link between subject and gang."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subject_gangs WHERE subject_id = ? AND gang_id = ?",
                       (subject_id, gang_id))
        self.conn.commit()

    def unlink_subject_from_location(self, subject_id: str, location_id: str):
        """Remove link between subject and location."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subject_locations WHERE subject_id = ? AND location_id = ?",
                       (subject_id, location_id))
        self.conn.commit()

    def unlink_subject_from_event(self, subject_id: str, event_id: str):
        """Remove link between subject and event."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subject_events WHERE subject_id = ? AND event_id = ?",
                       (subject_id, event_id))
        self.conn.commit()

    def unlink_subject_from_vehicle(self, subject_id: str, vehicle_id: str):
        """Remove link between subject and vehicle."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subject_vehicles WHERE subject_id = ? AND vehicle_id = ?",
                       (subject_id, vehicle_id))
        self.conn.commit()

    def unlink_subject_from_weapon(self, subject_id: str, weapon_id: str):
        """Remove link between subject and weapon."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subject_weapons WHERE subject_id = ? AND weapon_id = ?",
                       (subject_id, weapon_id))
        self.conn.commit()

    def unlink_gang_from_event(self, gang_id: str, event_id: str):
        """Remove link between gang and event."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM gang_events WHERE gang_id = ? AND event_id = ?",
                       (gang_id, event_id))
        self.conn.commit()

    def unlink_gang_from_location(self, gang_id: str, location_id: str):
        """Remove link between gang and location."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM gang_locations WHERE gang_id = ? AND location_id = ?",
                       (gang_id, location_id))
        self.conn.commit()

    def unlink_event_from_vehicle(self, event_id: str, vehicle_id: str):
        """Remove link between event and vehicle."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM event_vehicles WHERE event_id = ? AND vehicle_id = ?",
                       (event_id, vehicle_id))
        self.conn.commit()

    def unlink_event_from_weapon(self, event_id: str, weapon_id: str):
        """Remove link between event and weapon."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM event_weapons WHERE event_id = ? AND weapon_id = ?",
                       (event_id, weapon_id))
        self.conn.commit()

    def unlink_subjects(self, subject1_id: str, subject2_id: str):
        """Remove association between two subjects."""
        cursor = self.conn.cursor()
        cursor.execute("""DELETE FROM subject_associations
                          WHERE (subject1_id = ? AND subject2_id = ?)
                             OR (subject1_id = ? AND subject2_id = ?)""",
                       (subject1_id, subject2_id, subject2_id, subject1_id))
        self.conn.commit()

    def delete_charge_affiliate(self, affiliate_id: str):
        """Delete a charge affiliate (co-defendant) record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM charge_affiliates WHERE id = ?", (affiliate_id,))
        self.conn.commit()

    def get_gang_events(self, gang_id: str) -> list:
        """Get all events linked to a gang."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT e.* FROM events e
            JOIN gang_events ge ON e.id = ge.event_id
            WHERE ge.gang_id = ?
            ORDER BY e.event_date DESC
        """, (gang_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_gang_locations(self, gang_id: str) -> list:
        """Get all locations linked to a gang."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT l.* FROM locations l
            JOIN gang_locations gl ON l.id = gl.location_id
            WHERE gl.gang_id = ?
        """, (gang_id,))
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def close(self):
        """
        Close the database connection.

        Always call this when done with the database to ensure
        all changes are committed and resources are released.
        """
        if self.conn:
            self.conn.close()


# =============================================================================
# MODULE TESTING
# =============================================================================

if __name__ == "__main__":
    """
    Test database initialization when run directly.

    Usage: python database.py
    """
    db = TrackerDB()
    print("Database initialized successfully")
    print(f"Tables created in: {db.db_path}")
    db.close()
