import asyncio
import json
from pathlib import Path
from app.rag.retriever import ingest_legal_document

# ─── Seed Data: Ethiopian Laws ────────────────────────────────────────────────
# Each entry = one chunk. In production you'd parse PDFs/docs automatically.
# For now we seed with key Ethiopian proclamations manually.

ETHIOPIAN_LAWS = [
    # ── Land Lease ──────────────────────────────────────────────────────────
    {
        "id": "lease_proc_721_2011_art1",
        "source": "Proclamation No. 721/2011 – Urban Lands Lease Holding",
        "jurisdiction": "Ethiopia",
        "article": "Article 1 – Purpose",
        "text": (
            "This Proclamation is enacted to ensure that urban land, which is the property "
            "of the state and the people of Ethiopia, is administered in a manner that "
            "promotes sustainable urban development, ensures equitable access, and "
            "generates revenue for infrastructure investment."
        )
    },
    {
        "id": "lease_proc_721_2011_art5",
        "source": "Proclamation No. 721/2011 – Urban Lands Lease Holding",
        "jurisdiction": "Ethiopia",
        "article": "Article 5 – Lease Acquisition Methods",
        "text": (
            "Urban land shall be acquired through auction, tender, or negotiation. "
            "Auction is the primary method. Tender applies to investors with specific "
            "technical requirements. Negotiation is reserved for government and public "
            "interest projects. No person may hold urban land except through a lease "
            "agreement with the relevant urban administration."
        )
    },
    {
        "id": "lease_proc_721_2011_art23",
        "source": "Proclamation No. 721/2011 – Urban Lands Lease Holding",
        "jurisdiction": "Ethiopia",
        "article": "Article 23 – Lease Period",
        "text": (
            "The lease period for urban land shall be determined based on use: "
            "residential use up to 99 years; trade up to 70 years; industry up to 70 years; "
            "other urban services up to 70 years. The lease period begins from the date "
            "the land is handed over to the lessee."
        )
    },
    {
        "id": "lease_proc_721_2011_art40",
        "source": "Proclamation No. 721/2011 – Urban Lands Lease Holding",
        "jurisdiction": "Ethiopia",
        "article": "Article 40 – Termination of Lease",
        "text": (
            "A lease holding right may be terminated if: the lessee fails to pay the "
            "lease price within the prescribed period; the land is not developed as "
            "specified in the lease contract within the time allowed; the lessee "
            "uses the land for a purpose other than that specified in the contract; "
            "or the lease period expires without renewal."
        )
    },

    # ── Labour Law ──────────────────────────────────────────────────────────
    {
        "id": "labour_proc_1156_2019_art13",
        "source": "Labour Proclamation No. 1156/2019",
        "jurisdiction": "Ethiopia",
        "article": "Article 13 – Employment Contract",
        "text": (
            "An employment contract shall be in writing where the contract is for a "
            "definite period exceeding 45 days, or where the employee is required to "
            "work outside the place of recruitment. A contract of employment may be "
            "for a definite or indefinite period. Probation period shall not exceed "
            "60 working days."
        )
    },
    {
        "id": "labour_proc_1156_2019_art28",
        "source": "Labour Proclamation No. 1156/2019",
        "jurisdiction": "Ethiopia",
        "article": "Article 28 – Termination by Employer",
        "text": (
            "An employer may terminate an employment contract for just cause. Just cause "
            "includes: repeated failure to perform duties after warning; commission of "
            "crimes against the employer; absence without permission for more than 5 "
            "consecutive days; or inability to perform work due to non-work-related "
            "illness for more than 6 months. Termination without just cause entitles "
            "the employee to severance pay and compensation."
        )
    },
    {
        "id": "labour_proc_1156_2019_art39",
        "source": "Labour Proclamation No. 1156/2019",
        "jurisdiction": "Ethiopia",
        "article": "Article 39 – Severance Pay",
        "text": (
            "An employee whose contract is terminated is entitled to severance pay "
            "calculated as: 30 days' wages for the first year of service, and 10 days' "
            "wages for each subsequent year. Severance pay does not apply where the "
            "employee is terminated for serious disciplinary offence or voluntarily "
            "resigns."
        )
    },

    # ── Commercial Registration ─────────────────────────────────────────────
    {
        "id": "comm_reg_proc_980_2016_art4",
        "source": "Commercial Registration and Business Licensing Proclamation No. 980/2016",
        "jurisdiction": "Ethiopia",
        "article": "Article 4 – Obligation to Register",
        "text": (
            "Any person who intends to engage in commercial activity in Ethiopia must "
            "register with the relevant authority before commencing business. This "
            "includes sole traders, partnerships, private limited companies, and share "
            "companies. Failure to register is punishable by fine and closure of business."
        )
    },
    {
        "id": "comm_reg_proc_980_2016_art10",
        "source": "Commercial Registration and Business Licensing Proclamation No. 980/2016",
        "jurisdiction": "Ethiopia",
        "article": "Article 10 – Private Limited Company",
        "text": (
            "A private limited company (PLC) must have a minimum of 2 and maximum of 50 "
            "shareholders. The minimum capital is ETB 15,000. The company name must end "
            "with 'PLC'. Transfer of shares is restricted and requires consent of other "
            "shareholders. A PLC must maintain audited financial records annually."
        )
    },

    # ── Tenant / Rental ──────────────────────────────────────────────────────
    {
        "id": "rent_proc_addis_art7",
        "source": "Addis Ababa City Administration House Rent Regulation",
        "jurisdiction": "Ethiopia",
        "article": "Article 7 – Eviction",
        "text": (
            "A landlord may not evict a tenant without a valid court order. Notice of "
            "eviction must be given at least 30 days in advance for month-to-month "
            "tenancies and 90 days for yearly tenancies. Eviction for non-payment of "
            "rent requires the landlord to first issue a written warning and allow "
            "15 days to cure the default."
        )
    },
    {
        "id": "rent_proc_addis_art12",
        "source": "Addis Ababa City Administration House Rent Regulation",
        "jurisdiction": "Ethiopia",
        "article": "Article 12 – Rent Increase",
        "text": (
            "A landlord may increase rent only at the expiry of the rental agreement "
            "period. Mid-contract rent increases are prohibited. Written notice of rent "
            "increase must be given at least 60 days before the new period begins. "
            "Tenants who dispute the increase may appeal to the city administration "
            "housing authority."
        )
    },

    # ── Investment ───────────────────────────────────────────────────────────
    {
        "id": "invest_proc_1180_2020_art3",
        "source": "Investment Proclamation No. 1180/2020",
        "jurisdiction": "Ethiopia",
        "article": "Article 3 – Areas Reserved for Ethiopian Nationals",
        "text": (
            "The following sectors are reserved exclusively for Ethiopian investors: "
            "retail and wholesale trade; import and export trade (excluding certain "
            "categories); transport services (excluding air and sea transport); "
            "broadcasting; small-scale mining; legal and notarial services. Foreign "
            "investors may not engage in these reserved sectors."
        )
    },
    {
        "id": "invest_proc_1180_2020_art15",
        "source": "Investment Proclamation No. 1180/2020",
        "jurisdiction": "Ethiopia",
        "article": "Article 15 – Investment Incentives",
        "text": (
            "Registered investors in priority sectors are entitled to: income tax "
            "exemption for 2–7 years depending on sector and location; duty-free "
            "importation of capital goods and construction materials; loss carry-forward "
            "for the duration of the tax holiday; and export tax exemption. "
            "Priority sectors include manufacturing, agriculture, and ICT."
        )
    },
]


async def ingest_all():
    print(f"Starting ingestion of {len(ETHIOPIAN_LAWS)} legal document chunks...\n")

    success = 0
    failed = 0

    for i, law in enumerate(ETHIOPIAN_LAWS, 1):
        try:
            await ingest_legal_document(
                text=law["text"],
                source=law["source"],
                jurisdiction=law["jurisdiction"],
                article=law["article"],
                doc_id=law["id"]
            )
            print(f"  [{i:02d}/{len(ETHIOPIAN_LAWS)}] ✓  {law['source']} — {law['article']}")
            success += 1
        except Exception as e:
            print(f"  [{i:02d}/{len(ETHIOPIAN_LAWS)}] ✗  FAILED: {law['id']} → {e}")
            failed += 1

    print(f"\n{'─'*60}")
    print(f"Ingestion complete: {success} succeeded, {failed} failed")
    print(f"ChromaDB stored at: ./chroma_db")


if __name__ == "__main__":
    asyncio.run(ingest_all())