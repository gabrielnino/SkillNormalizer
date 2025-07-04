import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


class CategoryEditor:
    def __init__(self, root, hierarchy):
        self.root = root
        self.root.title("Category Hierarchy Editor")
        self.hierarchy = hierarchy
        self.tree = None
        self.selected_node = None
        self.setup_ui()
        self.load_hierarchy()

    def setup_ui(self):
        # Create main frames
        self.tree_frame = ttk.Frame(self.root)
        self.tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        # Treeview with scrollbar
        self.tree_scroll = ttk.Scrollbar(self.tree_frame)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(self.tree_frame, yscrollcommand=self.tree_scroll.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll.config(command=self.tree.yview)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Control buttons
        ttk.Button(self.control_frame, text="Add Category", command=self.add_category).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Add Term", command=self.add_term).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Edit", command=self.edit_item).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Remove", command=self.remove_item).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Move Up", command=self.move_up).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Move Down", command=self.move_down).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Save", command=self.save_hierarchy).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Expand All", command=self.expand_all).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_frame, text="Collapse All", command=self.collapse_all).pack(fill=tk.X, pady=2)

        # Status bar
        self.status = ttk.Label(self.control_frame, text="Ready")
        self.status.pack(fill=tk.X, pady=5)

    def load_hierarchy(self, parent="", hierarchy=None):
        if hierarchy is None:
            hierarchy = self.hierarchy

        for key, value in hierarchy.items():
            if isinstance(value, dict):
                node = self.tree.insert(parent, "end", text=key, values=("category",), open=False)
                self.load_hierarchy(node, value)
            elif isinstance(value, list):
                node = self.tree.insert(parent, "end", text=key, values=("term_list",), open=False)
                for term in value:
                    self.tree.insert(node, "end", text=term, values=("term",))

    def on_tree_select(self, event):
        self.selected_node = self.tree.focus()
        if self.selected_node:
            node_type = self.tree.item(self.selected_node, "values")[0]
            self.status.config(text=f"Selected: {self.tree.item(self.selected_node, 'text')} ({node_type})")

    def add_category(self):
        if not self.selected_node:
            parent = ""
        else:
            parent = self.selected_node
            node_type = self.tree.item(parent, "values")[0]
            if node_type == "term":
                messagebox.showerror("Error", "Cannot add category under a term")
                return

        name = simpledialog.askstring("Add Category", "Enter category name:")
        if name:
            self.tree.insert(parent, "end", text=name, values=("category",), open=True)
            self.status.config(text=f"Added category: {name}")

    def add_term(self):
        if not self.selected_node:
            messagebox.showerror("Error", "Please select a category to add terms to")
            return

        node_type = self.tree.item(self.selected_node, "values")[0]
        if node_type != "term_list":
            # If selected node is a category, find or create its term list
            has_term_list = False
            for child in self.tree.get_children(self.selected_node):
                if self.tree.item(child, "values")[0] == "term_list":
                    self.selected_node = child
                    has_term_list = True
                    break

            if not has_term_list:
                self.selected_node = self.tree.insert(
                    self.selected_node, "end",
                    text="Terms",
                    values=("term_list",),
                    open=True
                )

        term = simpledialog.askstring("Add Term", "Enter term:")
        if term:
            self.tree.insert(self.selected_node, "end", text=term, values=("term",))
            self.status.config(text=f"Added term: {term}")

    def edit_item(self):
        if not self.selected_node:
            return

        current_text = self.tree.item(self.selected_node, "text")
        node_type = self.tree.item(self.selected_node, "values")[0]

        if node_type == "term":
            new_text = simpledialog.askstring("Edit Term", "Edit term:", initialvalue=current_text)
        else:
            new_text = simpledialog.askstring("Edit Category", "Edit name:", initialvalue=current_text)

        if new_text and new_text != current_text:
            self.tree.item(self.selected_node, text=new_text)
            self.status.config(text=f"Renamed to: {new_text}")

    def remove_item(self):
        if not self.selected_node:
            return

        node_type = self.tree.item(self.selected_node, "values")[0]
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete this {node_type} and all its children?",
            icon="warning"
        )
        if confirm:
            self.tree.delete(self.selected_node)
            self.selected_node = None
            self.status.config(text="Item deleted")

    def move_up(self):
        if not self.selected_node:
            return

        parent = self.tree.parent(self.selected_node)
        if not parent:
            return

        siblings = list(self.tree.get_children(parent))
        index = siblings.index(self.selected_node)
        if index > 0:
            self.tree.move(self.selected_node, parent, index - 1)
            self.status.config(text="Moved item up")

    def move_down(self):
        if not self.selected_node:
            return

        parent = self.tree.parent(self.selected_node)
        if not parent:
            return

        siblings = list(self.tree.get_children(parent))
        index = siblings.index(self.selected_node)
        if index < len(siblings) - 1:
            self.tree.move(self.selected_node, parent, index + 1)
            self.status.config(text="Moved item down")

    def save_hierarchy(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")],
            title="Save Hierarchy"
        )
        if file_path:
            hierarchy = self.reconstruct_hierarchy()
            with open(file_path, 'w') as f:
                f.write("CATEGORY_HIERARCHY = ")
                json_str = json.dumps(hierarchy, indent=4)
                # Fix some formatting issues
                json_str = json_str.replace('": {', '": {')
                json_str = json_str.replace('"},', '"},')
                json_str = json_str.replace('"],', '"],')
                f.write(json_str)
                f.write("\n")
            self.status.config(text=f"Saved to {file_path}")

    def reconstruct_hierarchy(self, parent=""):
        children = self.tree.get_children(parent)
        if not children:
            return {}

        hierarchy = {}
        for child in children:
            node_type = self.tree.item(child, "values")[0]
            child_text = self.tree.item(child, "text")

            if node_type == "category":
                hierarchy[child_text] = self.reconstruct_hierarchy(child)
            elif node_type == "term_list":
                hierarchy[child_text] = [
                    self.tree.item(term, "text")
                    for term in self.tree.get_children(child)
                ]
        return hierarchy

    def expand_all(self):
        for node in self.tree.get_children():
            self.expand_node(node)

    def expand_node(self, node):
        self.tree.item(node, open=True)
        for child in self.tree.get_children(node):
            self.expand_node(child)

    def collapse_all(self):
        for node in self.tree.get_children():
            self.collapse_node(node)

    def collapse_node(self, node):
        self.tree.item(node, open=False)
        for child in self.tree.get_children(node):
            self.collapse_node(child)


# Your initial hierarchy
CATEGORY_HIERARCHY = {
    'TECHNICAL': {
        'PROGRAMMING': {
            '.NET': ['dotnet', 'csharp', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entityframework'],
            'JAVA_ECOSYSTEM': ['java', 'spring', 'spring boot', 'hibernate', 'j2ee', 'jakarta ee'],
            'PYTHON_ECOSYSTEM': ['python', 'django', 'flask', 'fastapi', 'numpy', 'pandas'],
            'JAVASCRIPT_TYPESCRIPT': ['javascript', 'typescript', 'ecmascript', 'es6'],
            'GO': ['golang', 'go'],
            'RUST': ['rust'],
            'RUBY': ['ruby', 'rails', 'ruby on rails'],
            'PHP': ['php', 'laravel', 'symfony'],
            'C_CPP': ['c', 'c\+\+', 'cplusplus', 'cpp'],
            'MOBILE': ['android', 'ios', 'flutter', 'react native', 'swift', 'kotlin'],
            'CONCEPTS': ['algorithms', 'data structures', 'design patterns', 'oop',
                         'object-oriented', 'solid principles', 'object oriented programming',
                         'object-oriented programming', 'object-oriented design']
        },
        'FRONTEND': {
            'FRAMEWORKS': ['react', 'angular', 'vue', 'svelte', 'ember'],
            'STYLING': ['css', 'sass', 'scss', 'less', 'bootstrap', 'tailwind'],
            'BUILD_TOOLS': ['webpack', 'vite', 'rollup', 'parcel'],
            'WEB_COMPONENTS': ['html', 'web components', 'shadow dom', 'custom elements'],
        },
        'BACKEND': {
            'APIS': ['rest', 'graphql', 'grpc', 'soap', 'openapi', 'swagger'],
            'SERVER': ['node', 'express', 'nestjs', 'koa', 'fastify'],
            'AUTH': ['oauth', 'jwt', 'openid connect', 'saml', 'ldap'],
            'MESSAGING': ['kafka', 'rabbitmq', 'nats', 'activemq'],
        },
        'DATA': {
            'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'postgresql', 'mssql', 'sql server', 'plsql'],
            'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb', 'dynamodb', 'firestore'],
            'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance', 'data warehouse'],
            'BIG_DATA': ['spark', 'hadoop', 'hive', 'hbase', 'bigquery'],
            'DATA_SCIENCE': ['pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn'],
        },
        'CLOUD': {
            'AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb', 'amazon web services', 'ec2', 'rds'],
            'AZURE': ['azure', 'functions', 'entra', 'sql database', 'microsoft azure', 'azure ad'],
            'GCP': ['gcp', 'google cloud', 'google cloud platform', 'bigtable', 'cloud functions'],
            'CLOUD_GENERAL': ['kubernetes', 'docker', 'serverless', 'paas', 'saas', 'iaas', 'cloud computing'],
        },
        'DEVOPS': {
            'CI_CD': ['ci/cd', 'jenkins', 'github actions', 'gitlab ci', 'circleci', 'continuous integration', 'ci/cd methodologies', 'ci/cd pipelines', 'ci/cd tools'],
            'INFRA_AS_CODE': ['terraform', 'pulumi', 'cloudformation', 'ansible'],
            'MONITORING': ['grafana', 'prometheus', 'datadog', 'new relic', 'splunk'],
            'VERSION_CONTROL': ['git', 'svn', 'mercurial', 'perforce'],
            'DEVOPS_GENERAL': ['git', 'svn', 'mercurial', 'perforce', 'devops', 'build pipelines', 'infrastructure as code'],
        },
        'TESTING': {
            'UNIT_TESTING': ['junit', 'nunit', 'pytest', 'mocha', 'jest'],
            'E2E_TESTING': ['selenium', 'cypress', 'playwright', 'testcafe'],
            'PERFORMANCE': ['jmeter', 'gatling', 'locust', 'k6'],
            'TEST_AUTOMATION': ['test automation', 'bdd', 'tdd', 'qa automation', 'automated testing'],
        },
        'ML_AI': {
            'MACHINE_LEARNING': ['machine learning', 'ml', 'tensorflow', 'pytorch', 'scikit-learn'],
            'DEEP_LEARNING': ['deep learning', 'neural networks', 'cnn', 'rnn'],
            'NLP': ['nlp', 'natural language processing', 'transformers', 'bert'],
            'COMPUTER_VISION': ['computer vision', 'opencv', 'object detection', 'image processing'],
            'AI_GENERAL': ['ai', 'artificial intelligence', 'llm', 'generative ai', 'chatgpt'],
        },
        'SECURITY': {
            'APP_SECURITY': ['owasp', 'security', 'penetration testing', 'vulnerability'],
            'IDENTITY': ['iam', 'rbac', 'sso', 'oauth', 'openid connect'],
            'CRYPTO': ['encryption', 'tls', 'ssl', 'cryptography', 'hashing'],
            'NETWORK_SEC': ['firewall', 'vpn', 'waf', 'ids', 'ips'],
        },
        'GAME_DEV': {
            'ENGINES': ['unreal', 'unity', 'godot', 'cryengine'],
            'GAMEPLAY': ['gameplay', 'physics', 'animation', 'ai'],
            'GRAPHICS': ['opengl', 'directx', 'vulkan', 'shaders'],
        },
        'EMBEDDED': {
            'IOT': ['iot', 'arduino', 'raspberry pi', 'embedded linux'],
            'FIRMWARE': ['firmware', 'rtos', 'bare metal'],
            'DRIVERS': ['device drivers', 'kernel development'],
        },
        'SYSTEM': {
            'DESIGN': ['system design', 'distributed systems', 'microservices',
                       'scalable architectures', 'event-driven architecture'],
            'TOOLS': ['powershell', 'visual studio', 'linux', 'cli', 'cmake'],
            'CONCEPTS': ['operating system', 'networking', 'file systems', 'multi-threaded']
        },
        'GENERAL_TECH': {
            'SOFTWARE_DEVELOPMENT': [
                'ability to refactor complex, monolithic systems',
                'developed high-quality, testable software',
                'solid background in data processing',
                'performance and memory optimization techniques',
                'performance optimization',
                'strong development background',
                'high-performance, memory efficient, multithreaded code',
                'high-performance, memory-efficient, multithreaded code',
                'multi-threaded software',
                'multithreaded code',
                'object-oriented design',
                'object-oriented design concepts',
                'object-oriented languages',
                'object-relational mapping',
                'oo design',
                'code quality and standards adherence',
                'code reviews',
                'coding standards and code reviews',
                'debugging',
                'debugging and optimization',
                'debugging and performance optimization',
                'debugging memory corruptions',
                'debugging tools',
                'algorithm optimization',
                'experience across the entire development lifecycle',
                'full software development life cycle experience',
                'use of software development tools',
                'well-designed code and solid programming skills'
            ],
            'WEB_DEVELOPMENT': [
                'back-end development',
                'back-end development with some front-end experience',
                'background in full stack development',
                'building web applications at scale',
                'experience building web applications',
                'front-end design',
                'front-end frameworks',
                'frontend technologies',
                'full-stack development',
                'full-stack web development',
                'modern frontend frameworks',
                'web application development',
                'web applications',
                'web development',
                'web frameworks',
                'web technologies',
                'html5',
                'html5+',
                'html5/css3',
                'css3+',
                'mvc',
                'ui frameworks',
                'ux design'
            ],
            'DATABASES': [
                'advanced experience in relational databases',
                'data capture',
                'data deduplication',
                'data storage',
                'database design and query optimization',
                'database development',
                'database management',
                'database optimization',
                'database optimization experience',
                'database software',
                'document databases',
                'experience working with databases',
                'experience working with relational databases',
                'has executed large scale data migrations',
                'proficiency with database operations and queries',
                'relational databases',
                'strong experience in relational databases',
                'understands large datasets and data mapping'
            ],
            'CLOUD_DEVOPS': [
                'bicep/arm templates',
                'containers',
                'continuous deployment',
                'designing ci/cd pipelines and build',
                'experience in ci/cd',
                'experience working with containers',
                'familiarity with ci/cd pipeline',
                'familiarity with containerization and orchestration',
                'proficient with ci/cd concepts and tooling',
                'build processes and testing',
                'build processes, testing, and operations experience',
                'build systems',
                'logging and telemetry',
                'monitoring tools',
                'source control',
                'source control management',
                'experience using source control software',
                'version control',
                'high availability systems',
                'high performing transaction systems',
                'scalability',
                'scalable frameworks',
                'system performance',
                'systems design',
                'systems design skills'
            ],
            'TESTING_QA': [
                'automated tests',
                'experience in fast-paced, test-driven, collaborative environments',
                'familiarity with test-driven development',
                'software testing and test-driven development',
                'test driven development',
                'test driven development techniques',
                'test framework design',
                'test framework design and development',
                'test frameworks',
                'test-driven development',
                'testing',
                'testing and debugging applications',
                'unit and integration testing',
                'unit testing',
                'unit testing, dependency injection, ci/cd',
                'unit/integration testing'
            ],
            'TOOLS_PLATFORMS': [
                'adobe experience manager',
                'adobe photoshop',
                'autocad/revit',
                'blender',
                'computer-aided design',
                'cad development',
                'copilot studio',
                'dynamics 365 business central/nav',
                'dynamics 365 f&o',
                'dynamics 365 finance & operations',
                'dynamics 365 finance and operations',
                'dynamics 365 sdk',
                'dynamics 365/crm',
                'gis systems',
                'experience using gis systems',
                'google analytics experience',
                'microsoft dataverse',
                'microsoft dynamics 365 ce',
                'next.js',
                'node.js',
                'nodejs',
                'opentext teamsite/livesite',
                'power apps',
                'power automate',
                'power pages',
                'power platform',
                'power platform experience',
                'react.js',
                'react.js/vue.js/angular.js',
                'reactive native technology',
                'salesforce',
                'salesforce data models',
                'sharepoint',
                'sharepoint online development experience',
                'shopify',
                'sketchup',
                'springboot',
                'ssrs',
                'ssrs, ssas, ssis',
                'starlims data model',
                'starlims qm v12',
                'vb.net',
                'vb.net experience',
                'visualforce',
                'vue.js',
                'wordpress',
                'x++',
                'x++ development'
            ],
            'SOFT_SKILLS': [
                'ability to build trusted relationships',
                'ability to coach and mentor',
                'ability to conduct remote sessions',
                'ability to empathize with users',
                'ability to manage multiple projects simultaneously',
                'ability to mentor and collaborate',
                'ability to multi-task',
                'ability to organize and prioritize work',
                'ability to work cross-functionally',
                'accountability',
                'attention to detail',
                'attention to detail and punctual',
                'collaborating with infrastructure team',
                'collaboration',
                'collaboration with cross-functional teams',
                'collaboration with global teams',
                'collaborative and dynamic skills',
                'collaborative and eager to contribute ideas',
                'collaborative and team-oriented',
                'collaborative team environment',
                'collaborative team environment experience',
                'collaborative team player',
                'collaborative teamwork',
                'conflict resolution and consensus building',
                'continuous improvement',
                'continuous learning and adaptability',
                'creativity',
                'critical thinker and problem solver',
                'curious, always learning',
                'demonstrated ability to communicate',
                'eager & willing to learn',
                'energy and passion',
                'english, both written and verbal',
                'enjoy working with diverse groups',
                'entrepreneurial mindset',
                'entrepreneurial spirit',
                'excellent organizational and time management skills',
                'excellent organizational skills',
                'excellent troubleshooting skills',
                'flexible scheduling',
                'growth mindset',
                'growth-oriented perspective',
                'initiative and results-driven',
                'initiative to manage your own workload',
                'influencing and reasoning skills',
                'organized',
                'organized with strong prioritization skills',
                'passion for learning and sharing knowledge',
                'passion for technology and code',
                'problem solver',
                'self-driven',
                'self-motivated and competent to work independently',
                'self-motivated and great organizational skills',
                'self-motivated and independent',
                'self-motivated and passionate about ui systems',
                'self-motivated and works with minimal supervision',
                'self-motivated, responsible, and a fast learner',
                'self-starter and key contributor',
                'smiling and making others smile',
                'strong sense of responsibility',
                'strong written and verbal communicator',
                'strong written and verbal english skills',
                'team player',
                'team work',
                'teamwork',
                'thrive in a collaborative environment',
                'user-focused, passionate, solutions-focused, and innovative',
                'working under pressure'
            ],
            'INDUSTRY_SPECIFIC': [
                '3d metrology',
                'adjustment to manufacturer\'s specifications',
                'ax',
                'big data analytics',
                'business and systems analysis',
                'business statistics',
                'business statistics knowledge',
                'care coordination',
                'care for people and user experience',
                'chemistry',
                'civil engineering',
                'cold calling',
                'cold calling and lead generation',
                'com',
                'comfort with technology',
                'community outreach',
                'demonstrated ability in cpr techniques',
                'demonstrated ability to operate related equipment',
                'demonstrated ndt skill, knowledge or experience',
                'demonstrated success in leading development teams',
                'desktop application development',
                'diagnostic and repair skills',
                'diagnostic radiographic/fluoroscopic procedures',
                'distributed applications',
                'ebpf',
                'emergency care',
                'erp development experience',
                'erp integration',
                'erp integration experience',
                'event marketing',
                'event set up and tear down',
                'expertise in chemistry',
                'expertise in windows development',
                'familiarity of modern cpu/gpu hardware architectures',
                'familiarity with cache stores',
                'familiarity with nginx',
                'familiarity with restful api design principles',
                'familiarity with ui development',
                'firewalls',
                'food preparation',
                'forklift operation',
                'foxpro',
                'game development',
                'game industry experience',
                'gdscript',
                'googletest',
                'grade 12 diploma or equivalent',
                'groovy',
                'hand-eye coordination',
                'high school diploma or ged',
                'high school diploma/ged',
                'identity and access management',
                'inspection and testing of mechanical units',
                'intermediate math skills',
                'kernel-level development',
                'kernel-mode drivers',
                'knowledge and experience applying disa stigs',
                'kql',
                'kvm hypervisor',
                'lead generation',
                'legally able to work in canada',
                'lighting and imaging understanding',
                'linkedin for recruiting',
                'low-level graphics apis',
                'macos/windows development',
                'malware analysis',
                'manual dexterity',
                'map-reduce',
                'marine engineering',
                'mdm frameworks',
                'mechanical aptitude',
                'mechanical knowledge',
                'meeting preparation and consultant engagement',
                'mentor and coach junior team members',
                'metadata-driven definitional development experience',
                'micro-services',
                'minimum of five years industry experience',
                'ndt methods expertise',
                'net development experience',
                'network programming',
                'network programming and kernel-level experience',
                'network protocols',
                'network protocols/socket programming',
                'networked game principles',
                'nursing interventions',
                'oncology nursing',
                'one or more scripting languages',
                'open source development',
                'open source experience and involvement',
                'open source frameworks',
                'operating radiographic and computerized imaging equipment',
                'operating systems concepts',
                'operational excellence',
                'operations experience',
                'patient assessment',
                'patient care and safety monitoring',
                'payments or financial systems experience',
                'payments or risk experience',
                'physical demands compliance',
                'physical stamina',
                'posix apis',
                'previous game design/development experience',
                'private connectivity',
                'process builders',
                'product demonstrations',
                'product knowledge',
                'professional appearance and conduct',
                'proficient with graphics debugging tools',
                'quality and process improvement',
                'radiation protection practices',
                'radiology information system',
                'real-time rendering',
                'recent experience using knockout.js',
                'recruiting',
                'redis',
                'relevant software programs',
                'research support',
                'routers, network switch development',
                'ror',
                'safety compliance',
                'scala',
                'scheduled maintenance',
                'secure coding practices',
                'secure software development',
                'service oriented architecture',
                'service-oriented architecture',
                'shell',
                'sidekiq',
                'soc architecture',
                'software architecture',
                'software system operation',
                'solution design',
                'strategic thinker and deadline-driven',
                'strong business partnership skills',
                'strong grasp of sockets',
                'strong low-level os internals in windows',
                'strong performance analysis',
                'structural engineering',
                'tcp/ip',
                'tcp/udp/ip',
                'technical support for existing applications',
                'threat modelling',
                'three years recent related oncology experience',
                'triggers',
                'unix o/s',
                'using kitchen tools',
                'valid driver\'s licence',
                'valid driver\'s license and insurability',
                'valid passport with no travel restrictions',
                'vnc, remote desktop protocol development',
                'vpc endpoints',
                'web api',
                'web api 2',
                'web services',
                'web services/web apis',
                'websocket',
                'windows api/win32/com',
                'windows internals',
                'windows kernel programming/driver development',
                'windows os development',
                'windows os kernel and driver development',
                'windows server engineering',
                'xml',
                'xslt'
            ],
            'LANGUAGE_LOCALIZATION': [
                'bilingual',
                'bilingualism in french and english',
                'fluency in french',
                'french language proficiency'
            ],
            'API_DEVELOPMENT': [
                'api and service-level validation',
                'api design',
                'api development',
                'apis',
                'event-driven architecture',
                'experience building restful apis',
                'expertise in developing apis',
                'familiarity with restful api design principles',
                'restful api',
                'restful api design',
                'restful api design principles',
                'restful apis',
                'experience in web services',
                'web services',
                'web services/web apis'
            ],
            'NETWORKING': [
                'dns',
                'firewalls',
                'http',
                'http protocol',
                'hypervisor technologies',
                'ip and network connectivity',
                'internet protocols',
                'private connectivity',
                'tcp/ip',
                'tcp/udp/ip',
                'vpc endpoints'
            ],
            'DOCUMENTATION_PORTFOLIO': [
                'a portfolio of past projects',
                'a portfolio of successful projects',
                'balance perfect vs getting it done'
            ]
        }
    },
    'NON_TECHNICAL': {
        'BUSINESS': ['sales', 'negotiation', 'client', 'customer', 'business development', 'account management'],
        'PROJECT_MGMT': ['project management', 'agile', 'scrum', 'kanban', 'waterfall'],
        'ANALYTICS': ['business intelligence', 'power bi', 'tableau', 'data visualization'],
        'OPERATIONS': ['logistics', 'supply chain', 'inventory', 'warehouse'],
        'EDUCATION': {
            'CERTIFICATION': ['degree', 'certification', 'bachelor', 'master', 'education'],
            'TEACHING': ['teaching', 'tutoring', 'mentoring', 'instruction']
        },
        'COMMUNICATION': ['communication', 'presentation', 'writing', 'documentation'],
        'LEADERSHIP': ['leadership', 'team building', 'mentoring', 'coaching'],
        'PROBLEM_SOLVING': ['problem solving', 'critical thinking', 'analytical']
    }
}

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("900x600")

    # Add some styling
    style = ttk.Style()
    style.configure("Treeview", font=('Arial', 10))
    style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))

    editor = CategoryEditor(root, CATEGORY_HIERARCHY)
    root.mainloop()