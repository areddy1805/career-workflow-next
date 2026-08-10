# ai_fde_eval_v1 — Labeled evaluation dataset (Phase B)

Source run: `20260810T004012474615Z` — 123 records.
Ground truth: **human judgment** from JD evidence + candidate profile (Pune, 5yrs exp, 3yrs GenAI/RAG/agentic, Azure, Python/FastAPI/LangChain/LangGraph). NOT derived from the current LLM score.

## Bucket composition

| bucket | count |
|---|---|
| excellent-ai | 22 |
| excellent-fde | 20 |
| excellent-ai-fde | 0 |
| ai-adjacent | 20 |
| generic-engineering | 20 |
| false-positive-ai | 20 |
| non-target | 21 |

## Labels

| job_id | title | company | status | rank | score | family | depth | fde | tech | traj | rank_band | rationale |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 070826911154 | Data Technology Consultant (AI Consultant) | Epam Systems | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | LOW | Epam Data Technology Consultant (AI Consultant): 18-23yrs, business case, regulated AI. FDE but seniority mismatch (too senior). |
| 070826040230 | Fullstack Developer (Java+React) | Integrated Personnel Services | SELECTED | 1 | 99.83 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | IPS Fullstack (Java+React): Java/Spring/SQL full-stack; 'AI exposure' mention only. Depth 1. RANKED #1 — contamination. |
| 230426030136 | .Net Fullstack | Qentelli | SELECTED | 6 | 97.38 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Qentelli .Net Fullstack: Playwright/Python automation engineer JD — neither .NET nor AI. Depth 0-1. |
| 080826015370 | Senior Software Engineer - Java, Python, React & cloud | Optum | SELECTED | 5 | 97.1 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Optum Senior SWE Java/Python/React & cloud: generic polyglot backend/full-stack. Depth 1. |
| 070826909440 | Python Next JS Senior Developer | CGI | SELECTED | 13 | 100.0 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | CGI Python Next JS Developer: consulting full-stack, generic. Depth 1. |
| 070826504113 | Full Stack Engineer | TekWissen | SELECTED | 17 | 99.05 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | TekWissen Full Stack Engineer: Azure hosting, CI/CD, generic full-stack. Depth 1. |
| 080826013468 | Java Full Stack Developer | Cloudxtreme | SELECTED | 28 | 100.0 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Cloudxtreme Java Full Stack Developer: generic Java FS. Depth 0-1. |
| 300426012743 | Java Full Stack Developer | Cloudxtreme | SELECTED | 30 | 100.0 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Cloudxtreme Java Full Stack Developer (dup-ish). Depth 0-1. |
| 070826039812 | Senior Software Developer | Independent Recruitment Consultant (freelancer) | SELECTED | 34 | 100.0 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Laravel/PHP Senior Software Developer: full-stack PHP. Depth 0. |
| 070826930353 | Senior backend Java developer - CLM | Luxoft | SELECTED | 37 | 100.0 | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Luxoft Senior Java backend - CLM: enterprise backend. Depth 0-1. |
| 070826040497 | Java Full Stack Developer-S | Infosys | REJECTED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Infosys Java Full Stack Developer-S: generic FS. Depth 1. |
| 080826015885 | Java+Spring Boot+React Developer | Infosys | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Infosys Java+Spring Boot+React Developer: generic FS. Depth 0. |
| 080826015892 | Java Developer-S | Infosys | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Infosys Java Developer: generic. Depth 0. |
| 090826000089 | Java Developer_S | Infosys | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Infosys Java Developer_S: generic. Depth 0. |
| 070826503383 | Java Developer | Redox Technologies | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Redox Java Developer: generic. Depth 0. |
| 070826502455 | TECHNICAL LEAD - ReactJS | Happiest Minds Technologies | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Happiest Minds Technical Lead ReactJS: frontend lead. Depth 0. |
| 070826503999 | Node.JS, MongoDB, Express.js, Passport.js, Mongoose professional | Casperon | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Casperon Node/Mongo/Express dev: generic backend. Depth 0. |
| 070826502867 | Full Stack Developer | Techefficio | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Techefficio Full Stack Developer: generic. Depth 0. |
| 070826930423 | Software Engineer - Java Full Stack, Angular, Kafka, CI/CD | Optum | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Optum Java Full Stack Angular Kafka: generic enterprise FS. Depth 0. |
| 070826930549 | Senior Software Engineer | Optum | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Optum Senior Software Engineer: generic enterprise SWE, no AI signals in JD. Depth 0-1. |
| 070826501554 | Software Engineer | Cognite | DEFERRED |  |  | GENERIC_ENGINEERING | 1 | NONE | LOW | LOW | LOW | Cognite Software Engineer: distributed systems/data eng, no AI. Depth 0-1. |
| 070826911605 | Senior Java Engineer – AI Native | Epam Systems | REJECTED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | REJECT | Epam Senior Java Engineer AI-Native: MCP servers, function calling, frontier models. GENUINE AI depth 4; rejected only as DESCRIPTION_DUPLICATE (dup listing) — correct rejection, role is excellent AI. |
| 070826011331 | Walk-in || Gen AI Developer | EY | REJECTED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | REJECT | EY Walk-in GenAI Developer: LangChain/LangGraph/AutoGen/Agent SDK/MCP. Genuine depth 4; rejected OBJECTIVELY_INCOMPATIBLE (walk-in venue) — correct per policy, not a quality rejection. |
| 070826013198 | RPA Engineer | Ensemble Health Partners | SELECTED | 7 | 99.13 | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Ensemble RPA Engineer: RPA ops (secrets, scheduling, logging) with open-source LLM 'exposure' — automation, not AI eng. Depth 1. RANKED #7 — contamination. |
| 070826501524 | SR RPA Developer | Aqilea | SELECTED | 44 | 99.13 | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Aqilea SR RPA Developer: RPA, not AI. Depth 0-1. SELECTED. |
| 070826911100 | Lead JavaScript Automation Test Engineer with AI & Agentic Testing | Epam Systems | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Epam Lead JS Automation Test Engineer with AI & Agentic Testing: TEST AUTOMATION, not AI engineering. Depth 1. |
| 070826038465 | QA Automation Tester - GenAI | PwC | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | PwC QA Automation Tester - GenAI: Playwright/POM testing with GenAI mentions. Depth 1. |
| 070826937128 | Packaged/SaaS Application Engineer | Accenture | SELECTED | 42 | 99.05 | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Accenture Packaged/SaaS Application Engineer: configure/support SaaS apps, low-code. Not AI. SELECTED #42. |
| 070826039496 | SAP Agentic AI Consultant Finance. | LTM | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | LTM SAP Agentic AI Consultant Finance: SAP consulting w/ agentic AI label. Depth 1. |
| 070826504597 | AI Data Specialist | Egadgetportal | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Egadgetportal AI Data Specialist: autonomous AI systems for client calls — vague 'data specialist' + AI buzz. Depth 1-2. |
| 070826500238 | AI/ML Model Development Expert | smartData Enterprises | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | smartData AI/ML Model Development Expert: recruiting-agency post, vague. Depth 1-2. |
| 070826935222 | AI/ML Expert | Purview Services | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Purview AI/ML Expert: staffing post w/ GenAI framework keywords, RAG mention but staffing context. Depth 1-2. |
| 050826935206 | Data For AI Testing Lead | Infosys | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Infosys Data For AI Testing Lead: testing data for AI — QA/data prep. Depth 1. |
| 070826504114 | Digital Technology Senior Specialist - Observability & AI Ops | Baker Hughes | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Baker Hughes DT Senior Specialist Observability & AI Ops: infrastructure observability ops. Depth 1. |
| 070826927116 | Customer Support Engineer | Hakimo | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Hakimo Customer Support Engineer: support role. Depth 0. |
| 080826011426 | Technical Support Engineer (Python | Full Stack) | Fabric | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Fabric Technical Support Engineer (Python|Full Stack): support-first. Depth 0-1. |
| 070826930609 | Customer Engineer | Applied Materials | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Applied Materials Customer Engineer: field service semiconductor (associate degree, military tech training). NOT FDE. Depth 0. |
| 070826503121 | Presales Engineer Juniper (Networking Solutions) | Thoughtsol Infotech | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Thoughtsol Presales Engineer Juniper (Networking Solutions): presales networking. Depth 0. |
| 070826030953 | Walk-in || Technical Product Owner (Azure) | Zinnov Management Consulting | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Zinnov Walk-in Technical Product Owner (Azure): PO role, rejected correctly (walk-in + non-engineering). Depth 0. |
| 080826009133 | ERPNext Developer | Talentrouters | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Talentrouters ERPNext Developer: ERP config/dev. Depth 0. |
| 070826501726 | Odoo Technical Consultant | Yantraadhigam Labs | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Yantraadhigam Odoo Technical Consultant: ERP consultant. Depth 0. |
| 080826015804 | IICS Developer | Infosys | DEFERRED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | Infosys IICS Developer: Informatica ETL integration. Depth 0. |
| 070826504455 | Consultant - Tech Consulting | EY | REJECTED |  |  | FALSE_POSITIVE | 1 | NONE | LOW | LOW | REJECT | EY Consultant Tech Consulting: engineering-agnostic consulting JD. Depth 0. |
| 070826911276 | Backend developer | Fan Tv Ai | DEFERRED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Fan Tv AI Backend Developer (Node/Express/Mongo): generic backend at AI company, no AI substance. Depth 1. |
| 080826011021 | HRMS Application Developer / Full Stack Developer | Shri Bajrang Power And Ispat Limited. | DEFERRED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Shri Bajrang HRMS Application Developer: HRMS app dev, non-target. |
| 070826930466 | COE Team Lead II | Uber | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Uber COE Team Lead: ops team lead, rejected correctly. |
| 090826002731 | Team Lead | Flipkart | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Flipkart Team Lead (wish master support): ops. |
| 080826010638 | Team Lead | Imarque Solutions | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Imarque Team Lead: BPO sales/contact center. |
| 070826500050 | Team Leader | Paytm | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Paytm Team Leader: communications/ops lead. |
| 070826911704 | Team Lead ( TL ) | Kriyalogic | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Kriyalogic Team Lead: BPO domestic process. |
| 070826036756 | Team Leader  BPO Recruitment | Wroots Global | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Wroots BPO Recruitment Team Leader: recruiting ops. |
| 070826503958 | Team Leader | Advertising Company In Mumbai | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Advertising Company Team Leader: sales. |
| 070826028767 | Team Lead | SPS Realty | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | SPS Realty Team Lead: realty sales. |
| 070826022541 | Team Lead | Aye Finance | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Aye Finance Team Lead: finance ops. |
| 070826014319 | Team Lead | Bharti AXA Life Insurance | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Bharti AXA Team Lead: insurance field. |
| 070826014142 | Team Lead | Bharti AXA Life Insurance | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Bharti AXA Team Lead (dup). |
| 070826027774 | Team Lead | Expect More Bpo Solutions | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Expect More BPO Team Lead: insurance/banking ops. |
| 070826911273 | Freelance Video Editor | Fan Tv Ai | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Fan Tv AI Freelance Video Editor: video editing, not engineering. |
| 070826504482 | Analyst - TAX - National - TAX - Indirect Tax | EY | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | EY Analyst Tax: tax, rejected correctly. |
| hiringcafe_ashby___bjakcareer___3a04559c-3700-429b-b2d2-1e144dc27611 | Ios Developer | BJAK | ROUTED_ATS | 113 |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | BJAK iOS Developer: mobile, wrong track. |
| hiringcafe_ashby___bjakcareer___ed731a5c-4614-4c9e-94fb-be8bbfd3ad54 | Mobile Engineer | BJAK | ROUTED_ATS | 114 |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | BJAK Mobile Engineer: mobile, wrong track. |
| 070826504033 | Sales Executive | Fractal Analytics | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Fractal Sales Executive: sales, rejected correctly (OBJECTIVELY_INCOMPATIBLE). |
| 070826500729 | Marketing Strategy and Analytics Manager | Twilio | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Twilio Marketing Strategy and Analytics Manager: marketing analytics, rejected correctly. |
| 070826500470 | Technical Account Manager (UiPath) | Wonderbotz | REJECTED |  |  | NON_TARGET | 0 | NONE | NONE | LOW | REJECT | Wonderbotz Technical Account Manager (UiPath): account management, not engineering. Rejected NON_SOFTWARE_ROLE. |
| 080826015330 | Full Stack Developer (React.js + Java Spring Boot + AI) | Ivorytusk Technologies | SELECTED | 25 | 99.19 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Ivorytusk Full Stack (React+Java Spring Boot+AI): AI label in title but JD is full-stack core; AI integration secondary. Depth 2. |
| 070826035400 | Full-Stack Developer (Node JS ) | Mobilytics Software (opc) | SELECTED | 27 | 99.3 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Mobilytics Full-Stack Node: builds AI-powered venture intelligence platform; AI-enabled product, backend role. Depth 2. |
| 070826039849 | Hiring Senior Full-Stack Software Engineer - WFO | Kozent Tec | SELECTED | 19 | 100.0 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Kozent Senior Full-Stack: US healthcare transcription AI-adjacent business. Generic full-stack core. Depth 1-2. |
| 080826011936 | Tech Lead- AI | Legato | SELECTED | 20 | 99.05 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Legato Tech Lead AI (Elevance Health): AI leadership but JD thin; likely AI-adjacent platform role. Depth 2. |
| 070826018850 | AI/ML Developer | Itcube Solutions | SELECTED | 38 | 100.0 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Itcube AI/ML Developer: build/deploy ML models + AI apps, Python/ML frameworks. Classic ML, not GenAI depth 2-3. |
| 070826930559 | ML Engineer | Luxoft | SELECTED | 48 | 99.05 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Luxoft ML Engineer: TensorFlow/PyTorch, MLflow, model serving — traditional ML + serving. Depth 3 (ML systems, not GenAI). |
| 070826500435 | Data Scientist - Generative AI | Kooe | SELECTED | 43 | 99.33 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Kooe Data Scientist - Generative AI: title suggests GenAI but DS framing. Depth 2. |
| 070826037807 | Ai Ml Engineer | Macsof | SELECTED | 45 | 99.13 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Macsof AI ML Engineer: generic AI/ML. Depth 2. |
| 090826002167 | Azure Data engineer + AI - 12th Aug (Wednesday) - Bengaluru- Virtual | Tata Consultancy Services | SELECTED | 14 | 99.05 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | TCS Azure Data Engineer + AI: primarily data pipelines (ADF/Databricks/Fabric), AI secondary. Depth 2. |
| 070826035483 | Customer Data Platform (CDP) Engineer | Photon | SELECTED | 47 | 99.53 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Photon CDP Engineer: customer data platform engineering — data/engineering, not AI modeling. Depth 1. |
| 070826040047 | Data Engineer | Teamplus Staffing Solution | SELECTED | 46 | 99.13 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Teamplus Data Engineer Cloud & Data Platform: data eng, not AI. Depth 1. |
| 070826039123 | Data Engineer Qnity | Affine Analytics | SELECTED | 49 | 99.13 | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Affine Data Engineer: data solutions, partner with business. Data eng depth 1. |
| 070826911615 | Lead Software Engineer – Java with GEN AI | Epam Systems | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Epam Lead Software Engineer Java with GEN AI: Java lead with GenAI exposure. Depth 2. |
| 070826502330 | Founding Backend Engineer | Coderound Ai | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Coderound Founding Backend Engineer: startup AI backend; role is backend eng in AI company. Depth 2. |
| 070826505141 | AI/ML Engineer | Bahwan CyberTek | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Bahwan CyberTek AI/ML Engineer: AI/ML engineering, depth varies 2-3. Classic ML probable. |
| 070826930461 | Associate AI/ML Engineer | Optum | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Optum Associate AI/ML Engineer: junior AI/ML. Depth 2. |
| 070826911685 | Senior AIML Python Engineer | Kriyalogic | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Kriyalogic Senior AIML Python Engineer: AIML python eng. Depth 2-3. |
| 080826015160 | AI Observability Engineer | Tata Consultancy Services | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | TCS AI Observability Engineer: supporting production AI apps — AI infra/ops. Depth 3 (AI infra). |
| 070826937581 | S&C Global Network - AI - T&O - Human Capital Analytics - Consultant | Accenture | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Accenture AI Human Capital Analytics Consultant: analytics consulting w/ AI toolkit. Depth 1-2. |
| 070826910883 | Data Consultant/ Data Engineer | Kennect Solutions | DEFERRED |  |  | AI_ADJACENT | 2 | LOW | MEDIUM | MEDIUM | STRONG | Kennect Data Consultant/Data Engineer: data pipelines + integrations, no AI. Depth 1. |
| 101225022689 | Senior AI Engineer | Ion Enterprise Solutions | SELECTED | 9 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Senior AI Engineer leading GenAI team; LLM/agentic/multimodal systems, OpenAI/Anthropic/Gemini/HF/LangChain. Core AI depth 4. |
| 070826911716 | Sr AI/Ml Engineer | Kriyalogic | SELECTED | 8 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Azure AI/Vertex AI enterprise AI, LLMs, RAG, MCP, agent workflows, Python APIs. Hands-on GenAI depth 4. |
| 070826027682 | ML/GenAI Engineer | Nisum | SELECTED | 12 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | ML/GenAI deployment, model serving, REST APIs, batch inference, Azure. AI depth 4. |
| 070826021427 | Generative Ai Developer | Tata Consultancy Services | SELECTED | 21 | 97.92 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | TCS GenAI Developer: LLMs, RAG pipelines, Agentic AI architectures, fine-tune NLP models. Depth 4. |
| 070826016191 | AI Engineer | Avisoft | SELECTED | 22 | 99.77 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Avisoft AI Engineer building enterprise GenAI solutions. Depth 4. |
| 070826502023 | AI / ML & Agentic AI Engineer | Innvonix Tech Solutions | SELECTED | 23 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | AI/ML & Agentic AI Engineer (Innvonix). Depth 4; thin JD but title+skills strong. |
| 080826010441 | Agentic AI | Dynpro | SELECTED | 33 | 98.31 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Dynpro Agentic Developer: build & productize agentic AI. Depth 4. |
| 070826930192 | Python GenAI Developer | Infosys | SELECTED | 36 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Infosys Python GenAI Developer: vector DBs (FAISS/Chroma/Pinecone), LangChain. Depth 4. |
| 080826013418 | Urgent hiring For _ AI/ML & Generative AI Consultant _ Python _ LLM | Sigma Allied Services | SELECTED | 32 | 99.13 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | AI/ML & GenAI Consultant: GenAI, LLMs, Azure OpenAI/Vertex, prompt eng, embeddings. Depth 4. |
| 070826035265 | Lead of AI Solutions R&D | Coventus AI Solutions Pvt Ltd | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Lead AI Solutions R&D: AWS/GCP, AI/ML certs; research+engineering. Depth 4. |
| 070826034413 | Developer | Dove Soft | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | AI Developer: FastAPI, OpenAI/Gemini/Claude, LangChain, RAG, vector DBs, AI agents. Depth 4. |
| 070826937563 | LLM Model Developer | Accenture | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Accenture LLM Model Developer: instruction fine-tuning, domain adaptation. Depth 4. |
| 070826909470 | Engineer, LLM Ops | Alegeus | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Alegeus Engineer LLM Ops: AI evaluation frameworks, monitoring, feedback loops. Depth 4 (AI infra/eval). |
| 120525010837 | Generative AI Engineer | Easemytrip | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Easemytrip GenAI Engineer: LangChain/LlamaIndex/HF/OpenAI/Anthropic; LLM/NLP backend. Depth 4. |
| 070826930680 | Senior AIML Engineer | Optum | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Optum Senior AIML: 8+ yrs AI/ML, NLP, OpenAI API, HF fine-tuning. Depth 4. |
| 070826930326 | Senior Software Engineer, AI Builder Experience (ABX) | Mongodb | DEFERRED |  |  | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | MongoDB AI Builder Experience: MCP servers, agent skills, polyglot backend. Depth 4. |
| 070826505022 | Lead I - ML Engineering(AI,ML,Python) | UST | SELECTED | 4 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | UST Lead ML Engineering: Agentic AI, PyTorch, RAG, Gen AI, deploy & build. Depth 4. |
| 080826009555 | Lead Data Scientist / Lead AI Engineer GenAI & Advanced ML | Go Digital Technology Consulting | SELECTED | 11 | 96.82 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Lead GenAI Engineer AWS: 5-9 yrs GenAI, RAG, LLM. Depth 4. |
| 070826018670 | Gen AI Developer | Coforge | SELECTED | 16 | 99.13 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Coforge Gen AI Developer: Azure, 4-10 yrs GenAI/LLM. Depth 4. |
| 070826016383 | Ai Ml Engineer | Sutherland | SELECTED | 15 | 99.05 | AI_ENGINEERING | 4 | NONE | EXCELLENT | EXCELLENT | TOP | Sutherland Applied AI Engineer: develops/deploys/operationalizes AI/ML solutions. Depth 4. |
| 190726002682 | Forward Deployed Engineer | 66degrees | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | 66degrees Forward Deployed Engineer: client interactions, production adoption, eval-driven roadmap. Textbook FDE. |
| 070826503457 | Forward Deployed Engineer Botminds | Botminds | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Botminds Forward Deployed Engineer: deployment at customer sites. Textbook FDE (Chennai). |
| 090826003001 | Forward Deployed Engineer | Quickhyre Ai | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Quickhyre Forward Deployed Engineer: AI/LLM model dev + API integration + deploy with teams. FDE+AI. |
| 090826002067 | Implementation Engineer | Invorit | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Invorit Implementation Engineer: understand customer problems on shop floor, solution design, implementation, commissioning, validation. Strong FDE. |
| 070826503593 | Implementation Engineer | Blueoptima | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Blueoptima Implementation Engineer: client onboarding, data quality, Tier 1 support — customer-facing technical. FDE MEDIUM-HIGH. |
| 070826500452 | Sr. Gen AI & Full Stack Solutions Engineer - Goa | SJ Innovation | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | SJ Innovation Sr Gen AI & Full Stack Solutions Engineer: React/Node/Mongo + GenAI APIs, client solutions. FDE+AI depth 3. |
| 250626016577 | AI Solutions Consultant- Immediate Joiners | CL Educate | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | CL Educate AI Solutions Consultant: customer-focused AI adoption, digital transformation. FDE MEDIUM-HIGH. |
| 070826500386 | Lead AI Solutions Consultant | Skan | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Skan Lead AI Solutions Consultant: build/deploy AI solutions, stakeholder collaboration. FDE HIGH. |
| jobspy_linkedin_li-4443541398 | Forward Deployment Engineer - Automation (Python) & Airflow | PTC | ROUTED_MANUAL | 58 |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | PTC Forward Deployment Engineer - Automation (Python) & Airflow: forward deployment + automation. FDE HIGH. |
| hiringcafe_brassring___25397___623208 | Ai Solutions Engineer | Deltek | ROUTED_MANUAL | 91 |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Deltek AI Solutions Engineer. FDE HIGH. |
| hiringcafe_zohorecruit___kanini___2887000032117627 | Forward Deployed Engineer | Kanini Software Solutions | ROUTED_MANUAL | 157 |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Kanini Forward Deployed Engineer. FDE HIGH. |
| hiringcafe_bamboohr___trustana___68 | Implementation Engineer | Trustana | ROUTED_MANUAL | 117 |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Trustana Implementation Engineer. FDE HIGH. |
| hiringcafe_oraclecloud___fa-emad-saasfaprod1.fa.ocs___5321 | Ai Business Solutions Engineer | Majesco | ROUTED_MANUAL | 163 |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Majesco AI Business Solutions Engineer. FDE HIGH. |
| 070826500374 | AI Solutions Architect | Yobitel Communications | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Yobitel AI Solutions Architect: design AI models, data pipelines, deploy ML. FDE+AI depth 3. |
| 070826910998 | Senior Software Engineer - Fulfillment Systems & Applied AI | LateShipment.com | SELECTED | 18 | 100.0 | FDE | 2 | HIGH | HIGH | HIGH | TOP | LateShipment Senior SWE Fulfillment & Applied AI: analyze business workflows, automation, stakeholders, U.S. experience — customer/problem-facing applied AI. AI_FDE. |
| jobspy_linkedin_li-4436172996 | Software Technical Consultant | PTC | ROUTED_MANUAL | 118 |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | PTC Software Technical Consultant: technical consulting/deployment. FDE MEDIUM. |
| 070826504225 | Technical Systems Engineer | Cisco | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Cisco Technical Systems Engineer: technical systems engineering. FDE MEDIUM. |
| 100826000022 | Senior Consultant Agentic AI & Web Data Engineer | Diligentminds Consulting | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Diligentminds Senior Consultant Agentic AI & Web Data Engineer: consulting + engineering. FDE+AI MEDIUM. |
| 070826033882 | Data Scientist (AI/ML) -  Consultant | Deloitte US-India Offices | DEFERRED |  |  | FDE | 2 | HIGH | HIGH | HIGH | TOP | Deloitte Data Scientist (AI/ML) Consultant: 4+ yrs building & deploying AI. Consulting-adjacent FDE MEDIUM. |
