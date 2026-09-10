from django.db import models
from django.utils.translation import gettext_lazy as _


class ReportStatus(models.TextChoices):
    """Status choices for reports."""

    PENDING = "PENDING", _("Pending")
    REVIEWED = "REVIEWED", _("Reviewed")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")


class ReportCondition(models.TextChoices):
    """Condition choices for reports."""

    NORMAL = "NORMAL", _("Normal")
    CAUTION = "CAUTION", _("Caution")
    CRITICAL = "CRITICAL", _("Critical")


class Category(models.TextChoices):
    """Category choices for analysis thresholds."""

    WEAR_METALS = "wear_metals", _("Wear Metals")
    CONTAMINATION = "contamination", _("Contamination")
    OIL_HEALTH = "oil_health", _("Oil Health")
    ADDITIVES = "additives", _("Additives")
    PARTICLE_ANALYSIS = "particle_analysis", _("Particle Analysis")
    FTIR = "ftir", _("FTIR Analysis")


class Parameter(models.TextChoices):
    """Parameter choices for analysis thresholds."""

    # Wear Metals
    IRON_FE = "iron_fe", _("Iron (Fe)")
    COPPER_CU = "copper_cu", _("Copper (Cu)")
    ALUMINUM_AL = "aluminum_al", _("Aluminum (Al)")
    CHROMIUM_CR = "chromium_cr", _("Chromium (Cr)")
    LEAD_PB = "lead_pb", _("Lead (Pb)")
    TIN_SN = "tin_sn", _("Tin (Sn)")
    NICKEL_NI = "nickel_ni", _("Nickel (Ni)")
    SILVER_AG = "silver_ag", _("Silver (Ag)")
    # Contamination
    SILICON_SI = "silicon_si", _("Silicon (Si)")
    SODIUM_NA = "sodium_na", _("Sodium (Na)")
    POTASSIUM_K = "potassium_k", _("Potassium (K)")
    BORON_B = "boron_b", _("Boron (B)")
    # Oil Health
    VISCOSITY_40C = "viscosity_40c", _("Viscosity @ 40C")
    VISCOSITY_100C = "viscosity_100c", _("Viscosity @ 100C")
    TBN = "tbn", _("TBN (Total Base Number)")
    TAN = "tan", _("TAN (Total Acid Number)")
    # FTIR
    OXIDATION = "oxidation", _("Oxidation")
    NITRATION = "nitration", _("Nitration")
    SULFATION = "sulfation", _("Sulfation")
    GLYCOL = "glycol", _("Glycol")
    FUEL_DILUTION = "fuel_dilution", _("Fuel Dilution")
    # Particle Analysis
    PQ_INDEX = "pq_index", _("PQ Index")
    # Additives
    ZINC_ZN = "zinc_zn", _("Zinc (Zn)")
    PHOSPHORUS_P = "phosphorus_p", _("Phosphorus (P)")
    MAGNESIUM_MG = "magnesium_mg", _("Magnesium (Mg)")
    CALCIUM_CA = "calcium_ca", _("Calcium (Ca)")
    MOLYBDENUM_MO = "molybdenum_mo", _("Molybdenum (Mo)")
    BARIUM_BA = "barium_ba", _("Barium (Ba)")
    CADMIUM_CD = "cadmium_cd", _("Cadmium (Cd)")
    TITANIUM_TI = "titanium_ti", _("Titanium (Ti)")
    VANADIUM_V = "vanadium_v", _("Vanadium (V)")
    MANGANESE_MN = "manganese_mn", _("Manganese (Mn)")
