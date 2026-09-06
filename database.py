import sqlite3
import os
import json

DB_PATH = "mca_assistant.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # =========================================================
    # USERS TABLE
    # =========================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =========================================================
    # SESSIONS TABLE
    # =========================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Add user_id column if old database does not have it
    try:
        cursor.execute("""
        ALTER TABLE sessions
        ADD COLUMN user_id TEXT REFERENCES users(id) ON DELETE CASCADE
        """)
    except sqlite3.OperationalError:
        pass

    # =========================================================
    # MESSAGES TABLE
    # =========================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    """)

    # =========================================================
    # SUBJECTS TABLE
    # =========================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        semester INTEGER NOT NULL,
        description TEXT,
        syllabus TEXT
    )
    """)

    # =========================================================
    # USER API CONFIG TABLE
    #
    # Each user gets their own OpenRouter API key and model.
    #
    # user A -> API key A
    # user B -> API key B
    # user C -> API key C
    # =========================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_api_config (
        user_id TEXT PRIMARY KEY,
        api_key TEXT NOT NULL,
        model TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # =========================================================
    # INDEXES
    # =========================================================
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sessions_user_id
    ON sessions(user_id)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_session_id
    ON messages(session_id)
    """)

    conn.commit()

    # =========================================================
    # SEED SUBJECTS
    # =========================================================
    cursor.execute("SELECT COUNT(*) FROM subjects")

    if cursor.fetchone()[0] == 0:
        seed_subjects(conn)

    conn.close()


# =============================================================
# SEED MCA SUBJECTS
# =============================================================

def seed_subjects(conn):

    subjects_data = [

        # =====================================================
        # SEMESTER 1
        # =====================================================

        {
            "code": "MCA-101",
            "name": "Mathematical Foundations of Computer Science",
            "semester": 1,
            "description": "Discrete Mathematics, Mathematical Logic, Graph Theory, and Algebraic Structures essential for understanding algorithm design and analysis.",
            "syllabus": [
                {
                    "unit": "Unit 1: Set Theory & Mathematical Logic",
                    "topics": [
                        "Propositional Logic",
                        "First-Order Logic",
                        "Truth Tables",
                        "Rules of Inference",
                        "Set Operations",
                        "Relations & Functions"
                    ]
                },
                {
                    "unit": "Unit 2: Combinatorics & Recurrence",
                    "topics": [
                        "Permutations and Combinations",
                        "Pigeonhole Principle",
                        "Generating Functions",
                        "Solving Linear Recurrence Relations"
                    ]
                },
                {
                    "unit": "Unit 3: Graph Theory",
                    "topics": [
                        "Graphs & Subgraphs",
                        "Isomorphism",
                        "Eulerian & Hamiltonian Paths",
                        "Planar Graphs",
                        "Trees & Spanning Trees",
                        "Kruskal's & Prim's Algorithms"
                    ]
                },
                {
                    "unit": "Unit 4: Algebraic Structures",
                    "topics": [
                        "Groups",
                        "Subgroups",
                        "Homomorphism",
                        "Rings & Fields",
                        "Lattices",
                        "Boolean Algebra"
                    ]
                }
            ]
        },

        {
            "code": "MCA-102",
            "name": "Data Structures and Algorithms",
            "semester": 1,
            "description": "Fundamental data structures and design of algorithms, complexity analysis, and implementation of core computing data types.",
            "syllabus": [
                {
                    "unit": "Unit 1: Introduction & Linear Structures",
                    "topics": [
                        "Algorithm Complexity",
                        "Big O Notation",
                        "Arrays",
                        "Singly/Doubly/Circular Linked Lists",
                        "Stack Applications",
                        "Queue Implementations"
                    ]
                },
                {
                    "unit": "Unit 2: Non-Linear Structures - Trees",
                    "topics": [
                        "Binary Trees",
                        "Binary Search Trees (BST)",
                        "AVL Trees",
                        "B-Trees & B+ Trees",
                        "Heap Trees",
                        "Tree Traversals (Inorder, Preorder, Postorder)"
                    ]
                },
                {
                    "unit": "Unit 3: Graphs",
                    "topics": [
                        "Graph Representations (Matrix/List)",
                        "Breadth First Search (BFS)",
                        "Depth First Search (DFS)",
                        "Dijkstra's Algorithm",
                        "Floyd-Warshall Algorithm"
                    ]
                },
                {
                    "unit": "Unit 4: Sorting & Searching",
                    "topics": [
                        "Bubble, Insertion, Selection Sort",
                        "Quick Sort",
                        "Merge Sort",
                        "Heap Sort",
                        "Linear and Binary Search",
                        "Hashing Techniques"
                    ]
                }
            ]
        },

        {
            "code": "MCA-103",
            "name": "Database Management Systems",
            "semester": 1,
            "description": "Concept, design, and implementation of relational databases, relational algebra, SQL, normalization theory, and database transactions.",
            "syllabus": [
                {
                    "unit": "Unit 1: DBMS Architecture & ER Modeling",
                    "topics": [
                        "File Systems vs. DBMS",
                        "Three-Schema Architecture",
                        "Data Independence",
                        "Entity-Relationship (ER) Model",
                        "Enhanced ER (EER) Concepts"
                    ]
                },
                {
                    "unit": "Unit 2: Relational Model & SQL",
                    "topics": [
                        "Relational Algebra",
                        "Relational Calculus",
                        "DDL/DML Commands",
                        "Subqueries & Joins",
                        "Views",
                        "Triggers",
                        "PL/SQL Blocks & Procedures"
                    ]
                },
                {
                    "unit": "Unit 3: Relational Database Design",
                    "topics": [
                        "Functional Dependencies",
                        "1NF, 2NF, 3NF",
                        "Boyce-Codd Normal Form (BCNF)",
                        "4NF & 5NF",
                        "Lossless Join Decomposition",
                        "Dependency Preservation"
                    ]
                },
                {
                    "unit": "Unit 4: Transaction & Concurrency Control",
                    "topics": [
                        "ACID Properties",
                        "Schedule Serializability",
                        "Locking Protocols (2PL)",
                        "Timestamp Ordering",
                        "Deadlock Handling",
                        "Database Backup & Recovery"
                    ]
                }
            ]
        },

        {
            "code": "MCA-104",
            "name": "Computer Organization & Architecture",
            "semester": 1,
            "description": "Internal hardware organization of computers, logic gates, assembly language concepts, memory hierarchy, and instruction processing units.",
            "syllabus": [
                {
                    "unit": "Unit 1: Digital Logic & Basic Components",
                    "topics": [
                        "Logic Gates",
                        "Karnaugh Maps (K-Maps)",
                        "Combinational Circuits (Multiplexers, Decoders, Adders)",
                        "Sequential Circuits (Flip-Flops, Registers, Counters)"
                    ]
                },
                {
                    "unit": "Unit 2: CPU Organization",
                    "topics": [
                        "Register Transfer Language",
                        "Instruction Codes & Cycles",
                        "Addressing Modes",
                        "Stack Organization",
                        "RISC vs. CISC Architectures"
                    ]
                },
                {
                    "unit": "Unit 3: Computer Arithmetic & Input-Output",
                    "topics": [
                        "Addition & Subtraction Algorithms",
                        "Booth's Multiplication Algorithm",
                        "Floating Point Arithmetic",
                        "Peripheral Devices",
                        "DMA Transfer",
                        "Interrupts"
                    ]
                },
                {
                    "unit": "Unit 4: Memory Organization",
                    "topics": [
                        "Memory Hierarchy",
                        "Main Memory (RAM/ROM)",
                        "Cache Memory Mapping (Direct, Associative, Set-Associative)",
                        "Virtual Memory",
                        "Paging & Segmentation"
                    ]
                }
            ]
        },

        {
            "code": "MCA-105",
            "name": "Object-Oriented Programming with Java",
            "semester": 1,
            "description": "Core object-oriented programming concepts using Java. Topics include inheritance, polymorphism, multithreading, exception handling, and collections.",
            "syllabus": [
                {
                    "unit": "Unit 1: Java Basics & OOP Concepts",
                    "topics": [
                        "JVM, JRE, JDK",
                        "Data Types & Operators",
                        "Classes and Objects",
                        "Constructors & Garbage Collection",
                        "Encapsulation",
                        "Method Overloading & Overriding"
                    ]
                },
                {
                    "unit": "Unit 2: Inheritance & Packages",
                    "topics": [
                        "Types of Inheritance",
                        "super & this keywords",
                        "Abstract Classes",
                        "Interfaces",
                        "Packages & Access Modifiers"
                    ]
                },
                {
                    "unit": "Unit 3: Exception Handling & Multithreading",
                    "topics": [
                        "Try-Catch-Finally",
                        "Custom Exceptions",
                        "Thread Life Cycle",
                        "Creating Threads (Thread class & Runnable)",
                        "Thread Synchronization",
                        "Inter-thread Communication"
                    ]
                },
                {
                    "unit": "Unit 4: I/O Streams & Java Collection Framework",
                    "topics": [
                        "File Handling",
                        "Byte and Character Streams",
                        "ArrayList, LinkedList",
                        "HashSet, TreeSet",
                        "HashMap, TreeMap",
                        "Generics"
                    ]
                }
            ]
        },

        # =====================================================
        # SEMESTER 2
        # =====================================================

        {
            "code": "MCA-201",
            "name": "Operating Systems",
            "semester": 2,
            "description": "Understanding OS roles, processes, threads, CPU scheduling, synchronization, deadlocks, memory management, and file systems.",
            "syllabus": [
                {
                    "unit": "Unit 1: Overview & Process Management",
                    "topics": [
                        "OS Functions",
                        "System Calls",
                        "Process Concept & States",
                        "Process Control Block (PCB)",
                        "CPU Scheduling Algorithms (FCFS, SJF, Priority, Round Robin)"
                    ]
                },
                {
                    "unit": "Unit 2: Process Synchronization & Deadlocks",
                    "topics": [
                        "Critical Section Problem",
                        "Semaphores",
                        "Monitors",
                        "Classic Synchronization Problems",
                        "Deadlock Characterization",
                        "Deadlock Prevention, Avoidance (Banker's), & Recovery"
                    ]
                },
                {
                    "unit": "Unit 3: Memory Management",
                    "topics": [
                        "Logical vs. Physical Address Space",
                        "Swapping",
                        "Contiguous Memory Allocation",
                        "Paging",
                        "Segmentation",
                        "Virtual Memory",
                        "Demand Paging",
                        "Page Replacement (FIFO, LRU, Optimal)"
                    ]
                },
                {
                    "unit": "Unit 4: File & Storage Systems",
                    "topics": [
                        "File Concept & Access Methods",
                        "Directory Structure",
                        "Allocation Methods (Contiguous, Linked, Indexed)",
                        "Free Space Management",
                        "Disk Scheduling (FCFS, SSTF, SCAN, LOOK)"
                    ]
                }
            ]
        },

        {
            "code": "MCA-202",
            "name": "Computer Networks",
            "semester": 2,
            "description": "Introduction to computer networks architecture, layers, communication protocols, addressing schemes, and security fundamentals.",
            "syllabus": [
                {
                    "unit": "Unit 1: Basics & Physical Layer",
                    "topics": [
                        "Data Communication Components",
                        "Network Topologies",
                        "LAN, WAN, MAN",
                        "OSI & TCP/IP Reference Models",
                        "Transmission Media (Coaxial, Fiber, Wireless)",
                        "Multiplexing"
                    ]
                },
                {
                    "unit": "Unit 2: Data Link Layer & MAC Sublayer",
                    "topics": [
                        "Error Detection & Correction (CRC, Hamming)",
                        "Flow Control (Stop & Wait, Go-Back-N, Selective Repeat)",
                        "ALOHA",
                        "CSMA/CD",
                        "CSMA/CA",
                        "Ethernet"
                    ]
                },
                {
                    "unit": "Unit 3: Network & Transport Layer",
                    "topics": [
                        "IPv4 & IPv6 Addressing",
                        "Subnetting",
                        "Routing Algorithms (Distance Vector, Link State)",
                        "TCP vs. UDP",
                        "Three-Way Handshake",
                        "Congestion Control"
                    ]
                },
                {
                    "unit": "Unit 4: Application Layer & Security",
                    "topics": [
                        "DNS",
                        "HTTP & HTTPS",
                        "SMTP, FTP",
                        "Symmetric & Asymmetric Cryptography",
                        "Firewalls",
                        "IPSec"
                    ]
                }
            ]
        },

        {
            "code": "MCA-203",
            "name": "Software Engineering & Agile Methodologies",
            "semester": 2,
            "description": "Software development life cycle, agile practices, software requirements, design modeling with UML, and software quality assurance.",
            "syllabus": [
                {
                    "unit": "Unit 1: Models & Agile Principles",
                    "topics": [
                        "Waterfall Model",
                        "Prototyping Model",
                        "Incremental & Spiral Models",
                        "Agile Software Development",
                        "Scrum Framework",
                        "Extreme Programming (XP)"
                    ]
                },
                {
                    "unit": "Unit 2: Requirements & Unified Modeling Language (UML)",
                    "topics": [
                        "SRS Document",
                        "Feasibility Study",
                        "Use Case Diagrams",
                        "Class Diagrams",
                        "Sequence & Collaboration Diagrams",
                        "State Chart Diagrams"
                    ]
                },
                {
                    "unit": "Unit 3: Software Design & Metrics",
                    "topics": [
                        "Cohesion & Coupling",
                        "Software Architecture Styles",
                        "Function Point (FP) Analysis",
                        "COCOMO Model"
                    ]
                },
                {
                    "unit": "Unit 4: Software Testing & Maintenance",
                    "topics": [
                        "White Box (Control Flow, Path) Testing",
                        "Black Box (Equivalence Partitioning, Boundary Value) Testing",
                        "Unit, Integration, System Testing",
                        "Regression Testing",
                        "Software Maintenance & Re-engineering"
                    ]
                }
            ]
        },

        {
            "code": "MCA-204",
            "name": "Web Technologies",
            "semester": 2,
            "description": "Modern web application development covering frontend basics, responsive design, JavaScript, client-side frameworks, backend integration with Node.js.",
            "syllabus": [
                {
                    "unit": "Unit 1: Frontend Basics",
                    "topics": [
                        "HTML5 Semantic Elements",
                        "CSS3 Selectors & Box Model",
                        "Flexbox & Grid Layouts",
                        "Responsive Web Design with Media Queries"
                    ]
                },
                {
                    "unit": "Unit 2: JavaScript & DOM",
                    "topics": [
                        "JS Data Types & Functions",
                        "ES6+ Features (Arrow Functions, Promises, Async/Await)",
                        "DOM Manipulation",
                        "Event Handling",
                        "AJAX & Fetch API"
                    ]
                },
                {
                    "unit": "Unit 3: Backend with Node.js & Express",
                    "topics": [
                        "Node.js Architecture",
                        "NPM Modules",
                        "Creating RESTful APIs with Express",
                        "Routing & Middleware",
                        "Handling CORS",
                        "JSON Web Tokens (JWT) for Auth"
                    ]
                },
                {
                    "unit": "Unit 4: Database Integration & Modern Frameworks",
                    "topics": [
                        "MongoDB CRUD Operations",
                        "Mongoose Schemas",
                        "Connecting Express to MongoDB",
                        "Introduction to React.js Components, State, & Props"
                    ]
                }
            ]
        },

        {
            "code": "MCA-205",
            "name": "Python Programming",
            "semester": 2,
            "description": "General-purpose programming using Python. Covers core concepts, file operations, web scraping, and data science libraries like Numpy and Pandas.",
            "syllabus": [
                {
                    "unit": "Unit 1: Python Core",
                    "topics": [
                        "Control Flow & Loops",
                        "Lists, Tuples, Dicts, Sets",
                        "List Comprehensions",
                        "Functions & Variable Scope",
                        "Module Import & Custom Modules"
                    ]
                },
                {
                    "unit": "Unit 2: OOP & File Operations",
                    "topics": [
                        "Classes & Objects",
                        "Inheritance & Polymorphism",
                        "File Handling (Read/Write text and JSON)",
                        "Exception Handling with try-except-finally"
                    ]
                },
                {
                    "unit": "Unit 3: Advanced Libraries & Web Scraping",
                    "topics": [
                        "Regular Expressions (re module)",
                        "Web Scraping with BeautifulSoup & requests",
                        "API Integration in Python"
                    ]
                },
                {
                    "unit": "Unit 4: Data Science Basics",
                    "topics": [
                        "NumPy Arrays & Math Operations",
                        "Pandas DataFrames",
                        "Data Cleaning & Filtering",
                        "Data Visualization with Matplotlib & Seaborn"
                    ]
                }
            ]
        },

        # =====================================================
        # SEMESTER 3
        # =====================================================

        {
            "code": "MCA-301",
            "name": "Design & Analysis of Algorithms",
            "semester": 3,
            "description": "Advanced algorithm analysis, dynamic programming, greedy strategies, NP-complete theory, and approximation algorithms.",
            "syllabus": [
                {
                    "unit": "Unit 1: Growth of Functions & Divide and Conquer",
                    "topics": [
                        "Asymptotic Notations",
                        "Substitution, Recursion Tree, & Master Theorem",
                        "Binary Search",
                        "Quick Sort & Merge Sort",
                        "Strassen's Matrix Multiplication"
                    ]
                },
                {
                    "unit": "Unit 2: Greedy & Dynamic Programming Strategies",
                    "topics": [
                        "Fractional Knapsack",
                        "Huffman Coding",
                        "Prim's & Kruskal's Algorithms",
                        "Matrix Chain Multiplication",
                        "0/1 Knapsack",
                        "Longest Common Subsequence (LCS)",
                        "Bellman-Ford Algorithm"
                    ]
                },
                {
                    "unit": "Unit 3: Backtracking & Branch & Bound",
                    "topics": [
                        "N-Queens Problem",
                        "Graph Coloring",
                        "Hamiltonian Cycle",
                        "Traveling Salesperson Problem (TSP)",
                        "Knapsack Branch and Bound"
                    ]
                },
                {
                    "unit": "Unit 4: NP-Completeness & Approximation",
                    "topics": [
                        "P, NP, NP-Hard, & NP-Complete classes",
                        "Polynomial Time Reductions",
                        "Satisfiability (SAT) Problem",
                        "Approximation Algorithms for TSP and Vertex Cover"
                    ]
                }
            ]
        },

        {
            "code": "MCA-302",
            "name": "Artificial Intelligence & Machine Learning",
            "semester": 3,
            "description": "Core concepts of AI search, knowledge representation, and supervised/unsupervised machine learning algorithms.",
            "syllabus": [
                {
                    "unit": "Unit 1: AI Search & Representation",
                    "topics": [
                        "State Space Search",
                        "Uninformed Search (BFS, DFS)",
                        "Informed Search (A*, AO*, Heuristics)",
                        "Adversarial Search (Minimax, Alpha-Beta Pruning)",
                        "First-Order Logic Resolution"
                    ]
                },
                {
                    "unit": "Unit 2: Supervised Learning",
                    "topics": [
                        "Linear & Logistic Regression",
                        "Decision Trees (ID3, C4.5)",
                        "Naïve Bayes Classifier",
                        "Support Vector Machines (SVM)",
                        "K-Nearest Neighbors (KNN)"
                    ]
                },
                {
                    "unit": "Unit 3: Unsupervised Learning & Evaluation",
                    "topics": [
                        "K-Means Clustering",
                        "Hierarchical Clustering",
                        "Principal Component Analysis (PCA)",
                        "Model Evaluation (Precision, Recall, F1-Score, ROC, Confusion Matrix)"
                    ]
                },
                {
                    "unit": "Unit 4: Neural Networks & Deep Learning",
                    "topics": [
                        "Perceptron",
                        "Multilayer Perceptron (MLP)",
                        "Backpropagation Algorithm",
                        "Introduction to Convolutional Neural Networks (CNN)",
                        "Natural Language Processing (NLP) Basics"
                    ]
                }
            ]
        },

        {
            "code": "MCA-303",
            "name": "Cloud Computing and DevOps",
            "semester": 3,
            "description": "Virtualization, cloud architectures (SaaS/PaaS/IaaS), major cloud providers, Docker containment, and Kubernetes automation with CI/CD.",
            "syllabus": [
                {
                    "unit": "Unit 1: Cloud Principles & Architectures",
                    "topics": [
                        "SaaS, PaaS, IaaS",
                        "Public, Private, Hybrid Clouds",
                        "Virtualization Concepts (Hypervisors)",
                        "Cloud Storage and Scalability"
                    ]
                },
                {
                    "unit": "Unit 2: Core AWS & Azure Services",
                    "topics": [
                        "AWS EC2 Instances",
                        "S3 Storage Buckets",
                        "IAM Roles & Security",
                        "Azure App Services",
                        "Serverless Computing (AWS Lambda)"
                    ]
                },
                {
                    "unit": "Unit 3: Containerization & Docker",
                    "topics": [
                        "Docker Architecture",
                        "Writing Dockerfiles",
                        "Docker Images & Containers",
                        "Docker Compose",
                        "Container Networking & Volumes"
                    ]
                },
                {
                    "unit": "Unit 4: Kubernetes & CI/CD",
                    "topics": [
                        "Kubernetes Architecture (Pods, Deployments, Services)",
                        "Introduction to CI/CD",
                        "GitHub Actions / Jenkins Pipelines",
                        "Infrastructure as Code (IaC) Basics"
                    ]
                }
            ]
        },

        {
            "code": "MCA-304",
            "name": "Cyber Security & Cryptography",
            "semester": 3,
            "description": "Threat landscapes, symmetric and asymmetric cryptosystems, message digests, network security controls, and cyber forensic standards.",
            "syllabus": [
                {
                    "unit": "Unit 1: Cryptographic Techniques",
                    "topics": [
                        "Symmetric Key Cryptography (DES, AES)",
                        "Asymmetric Key Cryptography (RSA)",
                        "Diffie-Hellman Key Exchange",
                        "Hash Functions (MD5, SHA-256)",
                        "Digital Signatures"
                    ]
                },
                {
                    "unit": "Unit 2: Network Security",
                    "topics": [
                        "Firewalls & Packet Filtering",
                        "Intrusion Detection Systems (IDS)",
                        "VPN & Tunneling Protocols",
                        "SSL/TLS handshake",
                        "WPA2 Wireless Security"
                    ]
                },
                {
                    "unit": "Unit 3: Attacks & Vulnerabilities",
                    "topics": [
                        "SQL Injection (SQLi)",
                        "Cross-Site Scripting (XSS)",
                        "Phishing & Social Engineering",
                        "DDoS Attacks",
                        "Buffer Overflow"
                    ]
                },
                {
                    "unit": "Unit 4: Cyber Law & Forensics",
                    "topics": [
                        "IT Act 2000 (India)",
                        "Digital Forensics Investigation Process",
                        "Data Recovery & Evidence Handling",
                        "Intellectual Property Rights (IPR)"
                    ]
                }
            ]
        },

        # =====================================================
        # SEMESTER 4
        # =====================================================

        {
            "code": "MCA-401",
            "name": "Big Data Analytics",
            "semester": 4,
            "description": "Hadoop file structures, MapReduce algorithms, Apache Spark analytics, and NoSQL databases for large dataset processing.",
            "syllabus": [
                {
                    "unit": "Unit 1: Big Data & Hadoop Ecosystem",
                    "topics": [
                        "V's of Big Data",
                        "Hadoop Distributed File System (HDFS)",
                        "NameNode & DataNode",
                        "Hadoop MapReduce Architecture"
                    ]
                },
                {
                    "unit": "Unit 2: Hive & Pig Scripts",
                    "topics": [
                        "Apache Hive (HQL, Managed vs External Tables)",
                        "Apache Pig (Latin Scripts, ETL flows)",
                        "Data ingestion with Sqoop & Flume"
                    ]
                },
                {
                    "unit": "Unit 3: Real-Time Analytics with Apache Spark",
                    "topics": [
                        "Spark Architecture",
                        "RDDs (Resilient Distributed Datasets)",
                        "Spark SQL & DataFrames",
                        "Spark Streaming Basics"
                    ]
                },
                {
                    "unit": "Unit 4: NoSQL Databases",
                    "topics": [
                        "Document Store (MongoDB)",
                        "Key-Value Store (Redis)",
                        "Column-Family (Cassandra)",
                        "CAP Theorem"
                    ]
                }
            ]
        },

        {
            "code": "MCA-402",
            "name": "Internet of Things",
            "semester": 4,
            "description": "IoT sensory components, microcontroller integration (Arduino/Raspberry Pi), wireless communication standards, and IoT analytics.",
            "syllabus": [
                {
                    "unit": "Unit 1: IoT Architecture & Sensors",
                    "topics": [
                        "Physical & Logical Design of IoT",
                        "IoT Enabling Technologies",
                        "Sensors (Temperature, Ultrasonic, PIR, LDR)",
                        "Actuators (Motors, Relays)"
                    ]
                },
                {
                    "unit": "Unit 2: Microcontrollers & Hardware platforms",
                    "topics": [
                        "Arduino UNO Board",
                        "Raspberry Pi Architecture",
                        "Interfacing Sensors with Microcontrollers",
                        "Python programming on Raspberry Pi"
                    ]
                },
                {
                    "unit": "Unit 3: IoT Communication Protocols",
                    "topics": [
                        "CoAP",
                        "MQTT Broker",
                        "ZigBee",
                        "Bluetooth Low Energy (BLE)",
                        "LoRaWAN"
                    ]
                },
                {
                    "unit": "Unit 4: IoT Applications & Security",
                    "topics": [
                        "Smart Home Systems",
                        "Smart Agriculture",
                        "Industrial IoT (IIoT)",
                        "IoT Privacy and Threat mitigation"
                    ]
                }
            ]
        }
    ]

    cursor = conn.cursor()

    for s in subjects_data:
        cursor.execute("""
        INSERT OR IGNORE INTO subjects
        (code, name, semester, description, syllabus)
        VALUES (?, ?, ?, ?, ?)
        """, (
            s["code"],
            s["name"],
            s["semester"],
            s["description"],
            json.dumps(s["syllabus"])
        ))

    conn.commit()


# =============================================================
# USER OPERATIONS
# =============================================================

def create_user(user_id, username, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO users
    (id, username, password_hash)
    VALUES (?, ?, ?)
    """, (
        user_id,
        username,
        password_hash
    ))

    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    WHERE username = ?
    """, (username,))

    row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    WHERE id = ?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None


# =============================================================
# USER API CONFIGURATION
# =============================================================

def save_user_api_config(user_id, api_key, model):
    """
    Save or update API configuration for ONE user.

    Each user has a separate row.

    User A:
        user_id = A
        api_key = KEY_A

    User B:
        user_id = B
        api_key = KEY_B
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO user_api_config
    (user_id, api_key, model, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)

    ON CONFLICT(user_id)
    DO UPDATE SET
        api_key = excluded.api_key,
        model = excluded.model,
        updated_at = CURRENT_TIMESTAMP
    """, (
        user_id,
        api_key,
        model
    ))

    conn.commit()
    conn.close()


def get_user_api_config(user_id):
    """
    Get API configuration belonging ONLY to the logged-in user.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT api_key, model
    FROM user_api_config
    WHERE user_id = ?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)

    return {}


def delete_user_api_config(user_id):
    """
    Delete API configuration for a specific user.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM user_api_config
    WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


# =============================================================
# SESSION CRUD OPERATIONS
# =============================================================

def create_session(session_id, user_id, title):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO sessions
    (id, user_id, title)
    VALUES (?, ?, ?)
    """, (
        session_id,
        user_id,
        title
    ))

    conn.commit()
    conn.close()


def get_sessions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, title, created_at
    FROM sessions
    WHERE user_id = ?
    ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()

    conn.close()

    return [dict(r) for r in rows]


def delete_session(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM sessions
    WHERE id = ?
    """, (session_id,))

    conn.commit()
    conn.close()


# =============================================================
# MESSAGE CRUD OPERATIONS
# =============================================================

def save_message(session_id, sender, content):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO messages
    (session_id, sender, content)
    VALUES (?, ?, ?)
    """, (
        session_id,
        sender,
        content
    ))

    conn.commit()
    conn.close()


def get_session_messages(session_id, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT sender, content, timestamp
    FROM messages
    WHERE session_id = ?
    ORDER BY id ASC
    """, (session_id,))

    rows = cursor.fetchall()

    conn.close()

    return [dict(r) for r in rows]


# =============================================================
# SUBJECT DATABASE OPERATIONS
# =============================================================

def get_subjects():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        code,
        name,
        semester,
        description,
        syllabus
    FROM subjects
    ORDER BY semester ASC, code ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    subjects = []

    for r in rows:
        subj = dict(r)

        try:
            subj["syllabus"] = json.loads(subj["syllabus"])
        except Exception:
            subj["syllabus"] = []

        subjects.append(subj)

    return subjects
