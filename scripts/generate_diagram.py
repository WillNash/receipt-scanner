#!/usr/bin/env python3
"""
Receipt Scanner — AWS Architecture Diagram
Generates architecture.png using matplotlib (no Graphviz dependency required).

Attempts the `diagrams` library first (requires Graphviz `dot` binary).
Falls back to a matplotlib-based renderer if Graphviz is absent.

Usage:
    python3 scripts/generate_diagram.py
Output:
    architecture.png  (in the repo root, landscape, ~2400×1400 px @ 150 dpi)
"""

import os
import sys
import subprocess
import shutil

# ---------------------------------------------------------------------------
# Helper: try the `diagrams` library path first
# ---------------------------------------------------------------------------

def try_diagrams_library(output_path: str) -> bool:
    """Return True if diagram was produced via the `diagrams` library."""
    if not shutil.which("dot"):
        print("INFO: Graphviz `dot` binary not found — skipping diagrams library path.")
        return False

    try:
        from diagrams import Diagram, Cluster, Edge
        from diagrams.aws.network import CloudFront, APIGateway
        from diagrams.aws.storage import S3
        from diagrams.aws.compute import Lambda
        from diagrams.aws.database import Dynamodb
        from diagrams.aws.integration import SQS
        from diagrams.aws.ml import Textract, Sagemaker
        from diagrams.aws.security import Cognito
        from diagrams.onprem.client import User
    except ImportError as exc:
        print(f"INFO: diagrams import failed ({exc}) — falling back to matplotlib.")
        return False

    base_name = output_path.replace(".png", "")
    graph_attr = {
        "rankdir": "LR",
        "splines": "ortho",
        "nodesep": "0.8",
        "ranksep": "1.4",
        "fontname": "Helvetica",
        "fontsize": "14",
        "pad": "0.6",
        "bgcolor": "#F8F9FA",
    }
    with Diagram(
        "Receipt Scanner — AWS Architecture",
        filename=base_name,
        outformat="png",
        graph_attr=graph_attr,
        show=False,
    ):
        browser = User("Browser / User")

        with Cluster("Auth"):
            cognito = Cognito("Cognito\nUser Pool")

        with Cluster("Frontend Delivery"):
            cf = CloudFront("CloudFront\n(OAC)")
            fe_bucket = S3("S3\nFrontend")
            cf >> fe_bucket

        with Cluster("API Layer"):
            apigw = APIGateway("API Gateway\nREST v1\n(POST /upload-url\nGET /jobs/{id}\nGET /receipts)")
            api_lambda = Lambda("Lambda\napi-handler\nPython 3.12")
            jobs_db = Dynamodb("DynamoDB\njobs table\n+ GSI")
            uploads_bucket = S3("S3\nUploads\n(presigned PUT)")
            apigw >> api_lambda
            api_lambda >> jobs_db
            api_lambda >> uploads_bucket

        with Cluster("Processing Pipeline"):
            sqs = SQS("SQS\nimage-jobs\n(DLQ included)")
            proc_lambda = Lambda("Lambda\nprocessor\nPython 3.12\nOpenCV crop")
            textract = Textract("Textract\nDetectDocumentText")
            bedrock = Sagemaker("Bedrock\nClaude Haiku")
            hashes_db = Dynamodb("DynamoDB\nimage-hashes")
            line_items_db = Dynamodb("DynamoDB\nline-items\n+ GSI")
            cropped_bucket = S3("S3 Uploads\n(cropped/\ndebug/ prefixes)")
            deployments_bucket = S3("S3 Deployments\n(processor.zip\n>70 MB)")

            sqs >> proc_lambda
            proc_lambda >> textract
            proc_lambda >> bedrock
            proc_lambda >> hashes_db
            proc_lambda >> jobs_db
            proc_lambda >> line_items_db
            proc_lambda >> cropped_bucket
            deployments_bucket >> Edge(label="s3_key deploy") >> proc_lambda

        # Cross-cluster edges
        browser >> cf
        browser >> Edge(label="OAuth2 code flow") >> cognito
        browser >> apigw
        uploads_bucket >> Edge(label="s3:ObjectCreated\nPUT") >> sqs

    print(f"SUCCESS: diagram written via `diagrams` library → {output_path}")
    return True


# ---------------------------------------------------------------------------
# Matplotlib fallback renderer
# ---------------------------------------------------------------------------

def draw_matplotlib_diagram(output_path: str) -> None:
    """Render a full AWS architecture diagram using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    # -----------------------------------------------------------------------
    # Colour palette (AWS-inspired)
    # -----------------------------------------------------------------------
    COLOURS = {
        "bg":          "#F8F9FA",
        "cluster_bg":  "#FFFFFF",
        "cluster_border": "#C8D6E5",

        # Service icon backgrounds (AWS brand colours per category)
        "networking":  "#8C4FFF",   # CloudFront, API Gateway — purple
        "storage":     "#3F8624",   # S3 — green
        "compute":     "#ED7100",   # Lambda — orange
        "database":    "#3B48CC",   # DynamoDB — blue
        "integration": "#E7157B",   # SQS — pink/red
        "security":    "#DD344C",   # Cognito — red
        "ml":          "#01A88D",   # Textract, Bedrock — teal
        "user":        "#555555",   # Browser — grey

        "text_light":  "#FFFFFF",
        "text_dark":   "#1A1A1A",
        "arrow":       "#445566",
        "dashed":      "#99AABB",
    }

    CLUSTER_COLOURS = {
        "user":       ("#E8F4FD", "#3498DB"),
        "auth":       ("#FDF2F8", "#8E44AD"),
        "frontend":   ("#E9F7EF", "#27AE60"),
        "api":        ("#FEF9E7", "#F39C12"),
        "processing": ("#FDEDEC", "#E74C3C"),
    }

    # -----------------------------------------------------------------------
    # Canvas setup — landscape 24×14 inches @ 150 dpi → 3600×2100 px
    # -----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(24, 14))
    fig.patch.set_facecolor(COLOURS["bg"])
    ax.set_facecolor(COLOURS["bg"])
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 14)
    ax.axis("off")

    # -----------------------------------------------------------------------
    # Drawing primitives
    # -----------------------------------------------------------------------

    def cluster_box(x, y, w, h, label, colour_key, zorder=1):
        bg, border = CLUSTER_COLOURS[colour_key]
        rect = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.15",
            linewidth=2,
            edgecolor=border,
            facecolor=bg,
            zorder=zorder,
            alpha=0.85,
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2, y + h - 0.22,
            label,
            ha="center", va="top",
            fontsize=9, fontweight="bold",
            color=border,
            zorder=zorder + 1,
        )

    def service_box(cx, cy, w, h, icon_label, name_label, cat, zorder=5):
        """Draw an AWS-style service icon box centred at (cx, cy)."""
        ic = COLOURS[cat]
        # Main box
        rect = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle="round,pad=0.08",
            linewidth=1.5,
            edgecolor=ic,
            facecolor=COLOURS["cluster_bg"],
            zorder=zorder,
        )
        ax.add_patch(rect)
        # Coloured top band (icon area)
        band_h = 0.42
        band = FancyBboxPatch(
            (cx - w / 2, cy + h / 2 - band_h), w, band_h,
            boxstyle="round,pad=0.0",
            linewidth=0,
            edgecolor=ic,
            facecolor=ic,
            zorder=zorder + 1,
            clip_on=True,
        )
        ax.add_patch(band)
        # Clip band to box top
        ax.text(
            cx, cy + h / 2 - band_h / 2,
            icon_label,
            ha="center", va="center",
            fontsize=8.5, fontweight="bold",
            color=COLOURS["text_light"],
            zorder=zorder + 2,
        )
        # Service name(s) below band
        lines = name_label.split("\n")
        n = len(lines)
        line_h = (h - band_h) / (n + 1)
        for i, line in enumerate(lines):
            ax.text(
                cx, cy + h / 2 - band_h - line_h * (i + 1) + line_h * 0.3,
                line,
                ha="center", va="center",
                fontsize=7.2,
                color=COLOURS["text_dark"],
                zorder=zorder + 2,
            )

    def arrow(x1, y1, x2, y2, label="", dashed=False, color=None, zorder=8):
        c = color or COLOURS["arrow"]
        style = dict(
            arrowstyle="->",
            color=c,
            linewidth=1.5,
            connectionstyle="arc3,rad=0.0",
        )
        if dashed:
            style["linestyle"] = "dashed"
            c = COLOURS["dashed"]
            style["color"] = c
        ax.annotate(
            "",
            xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->",
                color=c,
                lw=1.5,
                ls="--" if dashed else "-",
            ),
            zorder=zorder,
        )
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(
                mx, my + 0.13,
                label,
                ha="center", va="bottom",
                fontsize=6.2,
                color=c,
                style="italic",
                zorder=zorder,
                bbox=dict(boxstyle="round,pad=0.1", facecolor=COLOURS["bg"], edgecolor="none", alpha=0.7),
            )

    # -----------------------------------------------------------------------
    # Title
    # -----------------------------------------------------------------------
    ax.text(
        12, 13.7,
        "Receipt Scanner — AWS Architecture  (ap-southeast-2)",
        ha="center", va="top",
        fontsize=15, fontweight="bold",
        color=COLOURS["text_dark"],
    )

    # -----------------------------------------------------------------------
    # Cluster regions (drawn first, lowest z-order)
    # -----------------------------------------------------------------------
    # User/Auth cluster
    cluster_box(0.15, 5.8, 2.9, 7.7, "User & Auth", "user", zorder=1)
    # Frontend cluster
    cluster_box(3.25, 9.0, 3.6, 4.5, "Frontend Delivery", "frontend", zorder=1)
    # API layer cluster
    cluster_box(3.25, 1.5, 3.6, 7.2, "API Layer", "api", zorder=1)
    # Processing pipeline cluster
    cluster_box(7.1, 1.0, 16.6, 12.4, "Processing Pipeline", "processing", zorder=1)

    # -----------------------------------------------------------------------
    # Service boxes
    # -----------------------------------------------------------------------
    BW, BH = 2.0, 1.15   # standard box width / height

    # --- User layer ---
    # Browser
    service_box(1.6, 12.5, BW, BH, "USER", "Browser", "user")
    # Cognito
    service_box(1.6, 9.5, BW, BH, "COGNITO", "Cognito\nUser Pool", "security")

    # --- Frontend ---
    # CloudFront
    service_box(5.05, 12.5, BW, BH, "CLOUDFRONT", "CloudFront\n(OAC)", "networking")
    # S3 Frontend
    service_box(5.05, 10.5, BW, BH, "S3", "S3 Frontend\nBucket", "storage")

    # --- API layer ---
    # API Gateway
    service_box(5.05, 7.8, BW, BH, "API GW", "API Gateway\nREST v1", "networking")
    # Lambda API
    service_box(5.05, 5.8, BW, BH, "LAMBDA", "Lambda\napi-handler", "compute")
    # DynamoDB jobs
    service_box(5.05, 3.8, BW, BH, "DYNAMO", "DynamoDB\njobs table", "database")
    # S3 Uploads
    service_box(5.05, 1.9, BW, BH, "S3", "S3 Uploads\n(presigned PUT)", "storage")

    # --- Processing pipeline (right side) ---
    # SQS
    service_box(9.0, 4.5, BW, BH, "SQS", "SQS\nimage-jobs\n+ DLQ", "integration")
    # Lambda Processor
    service_box(12.0, 4.5, BW, BH, "LAMBDA", "Lambda\nprocessor\n(OpenCV crop)", "compute")
    # Textract
    service_box(15.2, 6.5, BW, BH, "TEXTRACT", "Textract\nDetectDocumentText", "ml")
    # Bedrock
    service_box(15.2, 4.5, BW, BH, "BEDROCK", "Bedrock\nClaude Haiku", "ml")
    # DynamoDB hashes
    service_box(18.5, 6.5, BW, BH, "DYNAMO", "DynamoDB\nimage-hashes", "database")
    # DynamoDB jobs (shared — arrow to existing box, note only)
    service_box(18.5, 4.5, BW, BH, "DYNAMO", "DynamoDB\njobs table\n(update status)", "database")
    # DynamoDB line items
    service_box(18.5, 2.4, BW, BH, "DYNAMO", "DynamoDB\nline-items\n+ GSI", "database")
    # S3 cropped/debug
    service_box(22.0, 5.5, BW, BH, "S3", "S3 Uploads\ncropped/ & debug/", "storage")
    # S3 deployments
    service_box(9.0, 2.2, BW, BH, "S3", "S3 Deployments\nprocessor.zip", "storage")

    # -----------------------------------------------------------------------
    # Arrows
    # -----------------------------------------------------------------------
    # Browser → CloudFront
    arrow(2.6, 12.5, 4.05, 12.5, "HTTPS")
    # Browser → Cognito (OAuth2 code flow, dashed)
    arrow(1.6, 11.93, 1.6, 10.08, "OAuth2 code flow", dashed=True)
    # Browser → API Gateway (via internet)
    arrow(2.6, 12.0, 4.05, 8.2, "HTTPS / JWT")
    # Cognito ← Lambda API (JWKS fetch, dashed)
    arrow(4.05, 5.8, 2.6, 9.5, "JWKS fetch\n(cold start)", dashed=True)

    # CloudFront → S3 Frontend
    arrow(5.05, 11.93, 5.05, 11.08, "OAC SigV4")
    # API GW → Lambda API
    arrow(5.05, 7.22, 5.05, 6.38, "AWS_PROXY")
    # Lambda API → DynamoDB jobs
    arrow(5.05, 5.22, 5.05, 4.38, "rate limits\n+ job write")
    # Lambda API → S3 Uploads (presigned URL)
    arrow(5.05, 3.22, 5.05, 2.48, "presigned PUT\nURL gen")

    # S3 Uploads → SQS (event notification)
    arrow(6.05, 1.9, 8.0, 4.5, "s3:ObjectCreated\n(PUT)")
    # SQS → Lambda Processor
    arrow(10.0, 4.5, 11.0, 4.5, "batch_size=1\nReportBatchItemFailures")
    # Lambda Processor → Textract
    arrow(13.0, 5.08, 14.2, 6.5, "DetectDocumentText")
    # Lambda Processor → Bedrock
    arrow(13.0, 4.5, 14.2, 4.5, "InvokeModel\n(Haiku)")
    # Lambda Processor → DynamoDB hashes
    arrow(16.2, 6.5, 17.5, 6.5, "dedup check\n+ write")
    # Lambda Processor → DynamoDB jobs (update)
    arrow(13.0, 4.2, 17.5, 4.5, "UpdateItem\n(status)")
    # Lambda Processor → DynamoDB line items
    arrow(13.0, 3.95, 17.5, 2.7, "PutItem\n(line items)")
    # Lambda Processor → S3 cropped/debug
    arrow(13.0, 4.8, 21.0, 5.5, "PutObject\ncropped/ debug/")
    # S3 deployments → Lambda Processor (deploy path, dashed)
    arrow(10.0, 2.2, 12.0, 3.93, "s3_key deploy\n(zip > 70 MB)", dashed=True)

    # -----------------------------------------------------------------------
    # Legend
    # -----------------------------------------------------------------------
    legend_x, legend_y = 0.2, 5.4
    legend_items = [
        ("networking",  "Networking"),
        ("compute",     "Compute"),
        ("storage",     "Storage"),
        ("database",    "Database"),
        ("integration", "Integration"),
        ("security",    "Security / Auth"),
        ("ml",          "ML / AI"),
    ]
    ax.text(legend_x, legend_y, "Legend", fontsize=8, fontweight="bold", color=COLOURS["text_dark"])
    for i, (cat, label) in enumerate(legend_items):
        lx = legend_x
        ly = legend_y - 0.52 - i * 0.52
        rect = mpatches.FancyBboxPatch(
            (lx, ly - 0.18), 0.35, 0.36,
            boxstyle="round,pad=0.04",
            facecolor=COLOURS[cat],
            edgecolor="none",
        )
        ax.add_patch(rect)
        ax.text(lx + 0.45, ly + 0.0, label, fontsize=7.2, va="center", color=COLOURS["text_dark"])

    # Solid vs dashed arrow legend
    arrow_y = legend_y - 0.52 - len(legend_items) * 0.52 - 0.1
    ax.annotate("", xy=(legend_x + 0.35, arrow_y), xytext=(legend_x, arrow_y),
                arrowprops=dict(arrowstyle="->", color=COLOURS["arrow"], lw=1.5))
    ax.text(legend_x + 0.45, arrow_y, "Data / control flow", fontsize=7.2, va="center", color=COLOURS["text_dark"])
    arrow_y2 = arrow_y - 0.45
    ax.annotate("", xy=(legend_x + 0.35, arrow_y2), xytext=(legend_x, arrow_y2),
                arrowprops=dict(arrowstyle="->", color=COLOURS["dashed"], lw=1.5, ls="--"))
    ax.text(legend_x + 0.45, arrow_y2, "Out-of-band / config", fontsize=7.2, va="center", color=COLOURS["text_dark"])

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    plt.tight_layout(pad=0.3)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=COLOURS["bg"])
    plt.close(fig)
    print(f"SUCCESS: diagram written via matplotlib → {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    output_path = os.path.join(repo_root, "architecture.png")

    print(f"Generating architecture diagram → {output_path}")

    if try_diagrams_library(output_path):
        return

    print("Using matplotlib renderer...")
    try:
        draw_matplotlib_diagram(output_path)
    except ImportError as exc:
        print(f"ERROR: matplotlib not available ({exc}).")
        print("Install it with: python3 -m pip install matplotlib --break-system-packages")
        sys.exit(1)

    if os.path.isfile(output_path):
        size_kb = os.path.getsize(output_path) // 1024
        print(f"File created: {output_path} ({size_kb} KB)")
    else:
        print("ERROR: output file was not created.")
        sys.exit(1)


if __name__ == "__main__":
    main()
