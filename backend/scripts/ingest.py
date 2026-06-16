"""
ingest.py
---------
Downloads legally-free UML reference material, splits it into chunks,
embeds each chunk with sentence-transformers, and stores everything in
a local ChromaDB collection.

Run once before starting the server:
    python -m scripts.ingest

Sources used (all public-domain or openly licensed):
  1. OMG UML 2.5.1 specification (publicly available PDF)
  2. PlantUML language reference (MIT-licensed docs)
  3. Mermaid.js documentation (MIT-licensed)
  4. Hand-written canonical UML examples (bundled below)
"""

import os
import re
import json
import hashlib
import textwrap
import requests
from pathlib import Path
from tqdm import tqdm

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
def _recursive_split(text: str, chunk_size: int, chunk_overlap: int, separators: list[str]) -> list[str]:
    """Minimal recursive character splitter (replaces langchain dependency)."""
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            chunks, current = [], ""
            for part in parts:
                candidate = (current + sep + part) if current else part
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    if len(part) > chunk_size:
                        chunks.extend(_recursive_split(part, chunk_size, chunk_overlap, separators[separators.index(sep)+1:] or [""]))
                        current = ""
                    else:
                        current = part
            if current:
                chunks.append(current)
            # apply overlap
            if chunk_overlap > 0:
                overlapped = []
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        tail = chunks[i-1][-chunk_overlap:]
                        chunk = tail + chunk
                    overlapped.append(chunk[:chunk_size] if len(chunk) > chunk_size else chunk)
                return overlapped
            return chunks
    # no separator found — hard split
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
CHROMA_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "uml_knowledge"
EMBED_MODEL = "all-MiniLM-L6-v2"   # fast, 384-dim, MIT license
CHUNK_SIZE = 600                    # characters
CHUNK_OVERLAP = 120

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Canonical UML examples – always bundled, never downloaded
# ---------------------------------------------------------------------------

CANONICAL_EXAMPLES = [
    # ---- Sequence diagrams ----
    {
        "title": "sequence_user_login",
        "type": "sequence",
        "description": "User login sequence diagram showing browser, auth server, and database interactions",
        "plantuml": textwrap.dedent("""\
            @startuml
            actor User
            participant Browser
            participant AuthServer
            participant Database

            User -> Browser: enter credentials
            Browser -> AuthServer: POST /login {username, password}
            AuthServer -> Database: SELECT user WHERE username=?
            Database --> AuthServer: user record
            AuthServer -> AuthServer: verify password hash
            alt credentials valid
                AuthServer --> Browser: 200 OK + JWT token
                Browser --> User: redirect to dashboard
            else credentials invalid
                AuthServer --> Browser: 401 Unauthorized
                Browser --> User: show error message
            end
            @enduml"""),
    },
    {
        "title": "sequence_api_call",
        "type": "sequence",
        "description": "REST API call sequence with error handling",
        "plantuml": textwrap.dedent("""\
            @startuml
            participant Client
            participant APIGateway
            participant Service
            participant Cache

            Client -> APIGateway: GET /resource/123
            APIGateway -> Cache: lookup key=resource:123
            alt cache hit
                Cache --> APIGateway: cached data
                APIGateway --> Client: 200 OK (cached)
            else cache miss
                Cache --> APIGateway: nil
                APIGateway -> Service: fetch resource 123
                Service --> APIGateway: resource data
                APIGateway -> Cache: set key=resource:123 TTL=300s
                APIGateway --> Client: 200 OK
            end
            @enduml"""),
    },
    # ---- Class diagrams ----
    {
        "title": "class_ecommerce",
        "type": "class",
        "description": "E-commerce domain class diagram with inheritance and associations",
        "plantuml": textwrap.dedent("""\
            @startuml
            abstract class User {
                +id: UUID
                +email: String
                +createdAt: DateTime
                +login(): Boolean
            }

            class Customer extends User {
                +shippingAddress: Address
                +placeOrder(): Order
            }

            class Admin extends User {
                +role: String
                +manageProducts(): void
            }

            class Order {
                +id: UUID
                +status: OrderStatus
                +total: Decimal
                +createdAt: DateTime
            }

            class OrderItem {
                +quantity: Integer
                +unitPrice: Decimal
            }

            class Product {
                +id: UUID
                +name: String
                +price: Decimal
                +stock: Integer
            }

            Customer "1" --> "0..*" Order : places
            Order "1" *-- "1..*" OrderItem : contains
            OrderItem "0..*" --> "1" Product : references
            @enduml"""),
    },
    {
        "title": "class_observer_pattern",
        "type": "class",
        "description": "Observer design pattern class diagram",
        "plantuml": textwrap.dedent("""\
            @startuml
            interface Subject {
                +attach(o: Observer): void
                +detach(o: Observer): void
                +notify(): void
            }

            interface Observer {
                +update(event: String): void
            }

            class ConcreteSubject implements Subject {
                -observers: List<Observer>
                -state: String
                +getState(): String
                +setState(s: String): void
            }

            class ConcreteObserverA implements Observer {
                -name: String
            }

            class ConcreteObserverB implements Observer {
                -logFile: String
            }

            ConcreteSubject "1" o-- "0..*" Observer : notifies
            @enduml"""),
    },
    # ---- Use-case diagrams ----
    {
        "title": "usecase_banking",
        "type": "usecase",
        "description": "Online banking use case diagram",
        "plantuml": textwrap.dedent("""\
            @startuml
            left to right direction
            actor Customer
            actor BankEmployee

            rectangle "Online Banking System" {
                usecase "View Balance" as UC1
                usecase "Transfer Funds" as UC2
                usecase "Pay Bill" as UC3
                usecase "View Transactions" as UC4
                usecase "Manage Accounts" as UC5
                usecase "Authenticate" as UC6
            }

            Customer --> UC1
            Customer --> UC2
            Customer --> UC3
            Customer --> UC4
            BankEmployee --> UC5
            UC1 .> UC6 : <<include>>
            UC2 .> UC6 : <<include>>
            UC3 .> UC6 : <<include>>
            @enduml"""),
    },
    # ---- Activity diagrams ----
    {
        "title": "activity_checkout",
        "type": "activity",
        "description": "E-commerce checkout activity diagram",
        "plantuml": textwrap.dedent("""\
            @startuml
            start
            :View cart;
            if (Cart empty?) then (yes)
                :Show empty cart message;
                stop
            else (no)
                :Enter shipping details;
                :Select shipping method;
                :Enter payment info;
                if (Payment valid?) then (yes)
                    :Process payment;
                    :Create order;
                    :Send confirmation email;
                    :Update inventory;
                    stop
                else (no)
                    :Show payment error;
                    :Return to payment step;
                endif
            endif
            @enduml"""),
    },
    # ---- Component diagrams ----
    {
        "title": "component_microservices",
        "type": "component",
        "description": "Microservices architecture component diagram",
        "plantuml": textwrap.dedent("""\
            @startuml
            package "Client Tier" {
                [Web App] as WEB
                [Mobile App] as MOB
            }

            package "API Gateway" {
                [Gateway] as GW
            }

            package "Services" {
                [User Service] as US
                [Order Service] as OS
                [Product Service] as PS
                [Notification Service] as NS
            }

            database "User DB" as UDB
            database "Order DB" as ODB
            database "Product DB" as PDB
            queue "Message Queue" as MQ

            WEB --> GW : HTTPS
            MOB --> GW : HTTPS
            GW --> US
            GW --> OS
            GW --> PS
            OS --> MQ : publish
            MQ --> NS : subscribe
            US --> UDB
            OS --> ODB
            PS --> PDB
            @enduml"""),
    },
    # ---- State diagrams ----
    {
        "title": "state_order",
        "type": "state",
        "description": "Order lifecycle state diagram",
        "plantuml": textwrap.dedent("""\
            @startuml
            [*] --> Pending : order created

            Pending --> Confirmed : payment received
            Pending --> Cancelled : user cancels / timeout

            Confirmed --> Processing : warehouse picks items
            Confirmed --> Cancelled : admin cancels

            Processing --> Shipped : carrier collected
            Processing --> Cancelled : items out of stock

            Shipped --> Delivered : carrier delivers
            Shipped --> Returned : customer refuses

            Delivered --> Returned : return request within 30d
            Returned --> Refunded : items inspected OK

            Cancelled --> [*]
            Delivered --> [*]
            Refunded --> [*]
            @enduml"""),
    },
    # ---- ER diagrams ----
    {
        "title": "er_blog",
        "type": "er",
        "description": "Blog platform entity-relationship diagram",
        "plantuml": textwrap.dedent("""\
            @startuml
            entity User {
                * id : UUID <<PK>>
                --
                * username : VARCHAR(50)
                * email : VARCHAR(255)
                * passwordHash : VARCHAR(255)
                createdAt : TIMESTAMP
            }

            entity Post {
                * id : UUID <<PK>>
                --
                * title : VARCHAR(255)
                * content : TEXT
                * publishedAt : TIMESTAMP
                status : ENUM(draft,published)
            }

            entity Comment {
                * id : UUID <<PK>>
                --
                * body : TEXT
                * createdAt : TIMESTAMP
            }

            entity Tag {
                * id : UUID <<PK>>
                --
                * name : VARCHAR(50)
            }

            User ||--o{ Post : writes
            User ||--o{ Comment : makes
            Post ||--o{ Comment : has
            Post }o--o{ Tag : tagged_with
            @enduml"""),
    },
]

# ---------------------------------------------------------------------------
# UML rules – distilled from OMG spec + PlantUML docs
# ---------------------------------------------------------------------------

UML_RULES = [
    {
        "title": "plantuml_sequence_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML Sequence Diagram Syntax Rules:
            - Every diagram starts with @startuml and ends with @enduml.
            - Participants are declared with: actor, participant, boundary, control, entity, database, collections, queue.
            - Arrows: -> synchronous, --> dashed/return, ->> async, x-> lost message.
            - Activation boxes: activate ParticipantName / deactivate ParticipantName.
            - Grouping: alt/else/end, loop, opt, par, break, critical, group.
            - Notes: note left/right/over ParticipantName : text.
            - Dividers: == phase name ==
            - Delay: ...5 minutes later...
            - Reference: ref over A,B : label
            Example minimal diagram:
            @startuml
            A -> B: call
            B --> A: reply
            @enduml"""),
    },
    {
        "title": "plantuml_class_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML Class Diagram Syntax Rules:
            - class, abstract class, interface, enum declarations.
            - Visibility: + public, - private, # protected, ~ package.
            - Relationships: --> association, ..> dependency, --|> inheritance (extends),
              ..|> realization (implements), *-- composition, o-- aggregation.
            - Multiplicity on relationships: "1" --> "0..*"
            - Namespace/package grouping: package "Name" { ... }
            - Notes: note on link / note left of ClassName
            - Generics: class Container<T>
            Example:
            @startuml
            class Animal {
                +name: String
                +sound(): String
            }
            class Dog extends Animal {
                +fetch(): void
            }
            @enduml"""),
    },
    {
        "title": "plantuml_usecase_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML Use Case Diagram Syntax Rules:
            - Actors: actor ActorName or actor "Long Name" as alias.
            - Use cases: usecase "UC Name" as UCAlias or (UC Name) shorthand.
            - Rectangle for system boundary: rectangle "System" { ... }
            - Relationships: --> association, .> with <<include>> or <<extend>> notes.
            - Include: (A) .> (B) : <<include>>   — B always executes as part of A.
            - Extend: (A) .> (B) : <<extend>>     — A conditionally extends B.
            - Inheritance between actors: ActorA --|> ActorB
            - Direction: left to right direction / top to bottom direction
            Example:
            @startuml
            left to right direction
            actor Customer
            rectangle Shop {
                usecase "Buy Item" as UC1
                usecase "Login" as UC2
            }
            Customer --> UC1
            UC1 .> UC2 : <<include>>
            @enduml"""),
    },
    {
        "title": "plantuml_activity_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML Activity Diagram Syntax (new beta syntax):
            - Start: start, End: stop or end.
            - Action: :Action label;
            - Decision: if (condition?) then (yes) ... else (no) ... endif
            - Loops: while (condition?) is (yes) ... endwhile
            - Fork/join: fork ... fork again ... end fork
            - Swimlanes: |SwimlaneName| before an action.
            - Notes: note right/left : text
            - Detach: detach (breaks flow from action)
            - Colors: #color on actions: :Action; #red
            Example:
            @startuml
            start
            :Receive request;
            if (Authorized?) then (yes)
                :Process;
                stop
            else (no)
                :Reject;
                stop
            endif
            @enduml"""),
    },
    {
        "title": "plantuml_component_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML Component Diagram Syntax Rules:
            - Components: [ComponentName] or component "Name" as alias.
            - Interfaces: () "InterfaceName" or interface "Name" as alias.
            - Packages/groups: package, node, folder, frame, cloud, database, rectangle.
            - Relationships: --> dependency/usage, --( provided interface, -( required interface.
            - Ports: [Comp] - [Port] : label
            - Notes work the same as other diagrams.
            Example:
            @startuml
            package "Backend" {
                [API] --> [Service]
                [Service] --> [Repository]
            }
            database "DB" as DB
            [Repository] --> DB
            @enduml"""),
    },
    {
        "title": "plantuml_state_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML State Diagram Syntax Rules:
            - States: state StateName or [*] for start/end pseudo-states.
            - Transitions: StateA --> StateB : trigger [guard] / action
            - Composite states: state "Name" as alias { ... }
            - Concurrent regions inside composite state: state "Name" { S1 \n -- \n S2 }
            - History: [H] for shallow, [H*] for deep history.
            - Entry/exit: state S : entry / action \n state S : exit / action
            Example:
            @startuml
            [*] --> Idle
            Idle --> Running : start
            Running --> Idle : stop
            Running --> [*] : complete
            @enduml"""),
    },
    {
        "title": "plantuml_er_syntax",
        "type": "rule",
        "content": textwrap.dedent("""\
            PlantUML Entity-Relationship (ER) Diagram via class diagram:
            - Use 'entity' keyword (same as class but semantically different).
            - Mark primary keys with <<PK>>, foreign keys with <<FK>>.
            - Cardinality: ||--|| one-to-one, ||--o{ one-to-many, }o--o{ many-to-many.
            - Crow's foot notation: | = exactly one, o = zero or one, { = many.
            - Fields separated by -- divider line: * mandatory, no * optional.
            Example:
            @startuml
            entity Order {
                * id : UUID <<PK>>
                --
                * customerId : UUID <<FK>>
                total : DECIMAL
            }
            entity Customer {
                * id : UUID <<PK>>
                --
                * name : VARCHAR
            }
            Customer ||--o{ Order : places
            @enduml"""),
    },
    {
        "title": "uml_design_principles",
        "type": "rule",
        "content": textwrap.dedent("""\
            General UML Design Principles (OMG UML 2.5.1):
            - Show only what is relevant to the view being modeled.
            - Sequence diagrams model time-ordered interactions between lifelines.
            - Class diagrams model static structure: classes, interfaces, and relationships.
            - Use case diagrams model functional requirements from an external perspective.
            - Activity diagrams model workflows and procedural logic.
            - Component diagrams model physical/logical architecture of a system.
            - State machine diagrams model behavior of a single entity across states.
            - Deployment diagrams model the physical allocation of artifacts to nodes.
            - A stereotype <<keyword>> adds semantic meaning to a model element.
            - Tagged values {key=value} attach properties to model elements.
            - Constraints [condition] restrict valid values or allowed states.
            - Use notes to explain non-obvious design decisions, never for code."""),
    },
    {
        "title": "common_diagram_selection_guide",
        "type": "rule",
        "content": textwrap.dedent("""\
            When to use each UML diagram type:
            - Sequence diagram: show HOW objects interact over time; API flows, login, checkout.
            - Class diagram: show WHAT entities exist and their relationships; domain model, design patterns.
            - Use case diagram: show WHO does WHAT; actor-system interactions, requirements overview.
            - Activity diagram: show flow of CONTROL or DATA; business processes, algorithms, workflows.
            - Component diagram: show software ARCHITECTURE; microservices, layers, modules.
            - State diagram: show LIFECYCLE of a single object; order status, UI states, protocol.
            - ER diagram: show DATABASE schema; tables, keys, cardinality.
            - Deployment diagram: show INFRASTRUCTURE; servers, containers, nodes, networks.
            Key rule: choose the diagram type that most directly answers the viewer's question
            about the system. Never add elements that are not relevant to that question."""),
    },
]


# ---------------------------------------------------------------------------
# Downloader helpers
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, label: str) -> bool:
    """Download url to dest. Returns True on success."""
    if dest.exists():
        print(f"  [skip] {label} already downloaded")
        return True
    try:
        print(f"  [download] {label} …")
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"  [ok] saved to {dest.name}")
        return True
    except Exception as e:
        print(f"  [warn] could not download {label}: {e}")
        return False


def extract_text_from_pdf(path: Path) -> str:
    """Extract plain text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n".join(pages)
    except Exception as e:
        print(f"  [warn] PDF extraction failed for {path.name}: {e}")
        return ""


def fetch_plantuml_docs() -> str:
    """Fetch the PlantUML language reference guide from GitHub (MIT)."""
    url = "https://raw.githubusercontent.com/plantuml/plantuml/master/docs/PlantUML_Language_Reference_Guide_en.md"
    dest = DATA_DIR / "plantuml_language_reference.md"
    ok = download_file(url, dest, "PlantUML Language Reference")
    if ok and dest.exists():
        return dest.read_text(errors="ignore")
    return ""


# ---------------------------------------------------------------------------
# Chunk + embed
# ---------------------------------------------------------------------------

def make_chunks(text: str, metadata: dict) -> list[dict]:
    """Split text into overlapping chunks; attach metadata to each."""
    raw_chunks = _recursive_split(
        text,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
    )
    result = []
    for i, chunk in enumerate(raw_chunks):
        chunk = chunk.strip()
        if len(chunk) < 60:          # skip tiny fragments
            continue
        chunk_id = hashlib.md5(chunk.encode()).hexdigest()[:12]
        result.append({
            "id": f"{metadata.get('title','doc')}_{i}_{chunk_id}",
            "text": chunk,
            "metadata": {**metadata, "chunk_index": i},
        })
    return result


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest():
    print("=" * 60)
    print("UML Knowledge Base Ingestion")
    print("=" * 60)

    # 1. Collect all documents
    all_chunks: list[dict] = []

    # --- Canonical examples ---
    print("\n[1] Loading canonical UML examples …")
    for ex in CANONICAL_EXAMPLES:
        text = f"Diagram type: {ex['type']}\nDescription: {ex['description']}\n\n{ex['plantuml']}"
        chunks = make_chunks(text, {
            "title": ex["title"],
            "source": "canonical_examples",
            "diagram_type": ex["type"],
            "content_type": "example",
        })
        all_chunks.extend(chunks)
    print(f"  {len(CANONICAL_EXAMPLES)} examples → {len(all_chunks)} chunks")

    # --- UML rules ---
    print("\n[2] Loading UML syntax rules …")
    rule_chunks_before = len(all_chunks)
    for rule in UML_RULES:
        text = f"{rule['title']}\n\n{rule['content']}"
        chunks = make_chunks(text, {
            "title": rule["title"],
            "source": "uml_rules",
            "diagram_type": rule.get("type", "general"),
            "content_type": "rule",
        })
        all_chunks.extend(chunks)
    print(f"  {len(UML_RULES)} rules → {len(all_chunks) - rule_chunks_before} chunks")

    # --- PlantUML docs (online, optional) ---
    print("\n[3] Fetching PlantUML language reference (optional) …")
    plantuml_text = fetch_plantuml_docs()
    if plantuml_text:
        chunks = make_chunks(plantuml_text, {
            "title": "plantuml_reference",
            "source": "plantuml_docs",
            "diagram_type": "general",
            "content_type": "documentation",
        })
        all_chunks.extend(chunks)
        print(f"  plantuml docs → {len(chunks)} chunks")
    else:
        print("  (skipped – no internet or file unavailable)")

    # 2. Embed
    print(f"\n[4] Embedding {len(all_chunks)} chunks with {EMBED_MODEL} …")
    model = SentenceTransformer(EMBED_MODEL)
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    # 3. Store in ChromaDB
    print(f"\n[5] Storing in ChromaDB at {CHROMA_DIR} …")
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    # Drop and recreate collection for clean re-ingestion
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Chroma expects lists, upload in batches
    BATCH = 256
    for start in tqdm(range(0, len(all_chunks), BATCH), desc="  uploading"):
        batch = all_chunks[start : start + BATCH]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=[embeddings[start + i].tolist() for i in range(len(batch))],
            metadatas=[c["metadata"] for c in batch],
        )

    # 4. Save manifest
    manifest = {
        "total_chunks": len(all_chunks),
        "embed_model": EMBED_MODEL,
        "collection": COLLECTION_NAME,
        "sources": list({c["metadata"]["source"] for c in all_chunks}),
    }
    manifest_path = BASE_DIR / "data" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"\n{'=' * 60}")
    print(f"Done! {len(all_chunks)} chunks stored in ChromaDB.")
    print(f"Manifest saved to {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    ingest()
