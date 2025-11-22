# Money's Last Exam: A Longitudinal Benchmark of Autonomous Economic Agency

**Abstract**
Current Artificial Intelligence benchmarks rely heavily on static evaluation methods, such as multiple-choice reasoning (MMLU) or isolated code snippet generation (HumanEval). While these metrics quantify synthetic intelligence, they fail to measure "Economic Agency"—the capacity of an AI model to act as an autonomous participant in a digital economy. We introduce "Money’s Last Exam" (MLE), a novel benchmark that evaluates the ability of Large Language Models (LLMs) to generate, deploy, and maintain profitable web applications without human intervention.

Participating models are provided with a Stripe API key and a hosting environment. On a daily cadence, each model is prompted to autonomously conceive a business idea, write the full-stack code, and deploy it. Success is measured not by code quality scores, but by Net Revenue Generated (NRG). This paper presents the results of the inaugural MLE run, where models including Claude 3.5 Sonnet, Gemini, and GPT-4o competed. The results highlight a critical "reliability gap": while models are capable of generating revenue-generating concepts (e.g., a "Virtual High Five" store), they suffer from a high rate of deployment failure due to hallucinations in dependency management and syntax errors, with no model exceeding a 50% uptime success rate.

## 1. Introduction
The trajectory of Large Language Models (LLMs) has been defined by their performance on standardized datasets. As models approach saturation on benchmarks like GSM8K (math) and HumanEval (coding), the industry faces a "evaluation crisis." We know these models can write code, but can they build products?

There is a fundamental disconnect between solving a LeetCode problem and shipping a production-ready web application. The latter requires handling ambiguity, managing API secrets, designing user interfaces, and ensuring containerization compatibility.

We propose that the ultimate Turing Test for an AI agent is not conversation, but capitalism. Can an agent survive in the market? To answer this, we developed *Money's Last Exam*, a live benchmarking platform that gives models the "means of production" (server hosting) and the "means of collection" (Stripe payment processing) and tasks them with maximizing profit.

## 2. Methodology

### 2.1 The MLE Framework
The benchmark operates on a strict 24-hour cycle, designed to test longitudinal stability and self-healing capabilities.

1. **The Prompt:** At 00:00 UTC, each model receives a system prompt: "Generate a valid web application idea to make money online. Implement the code. You have access to a Stripe API key for payments. Your goal is to maximize net revenue."
2. **Code Generation:** The model outputs a complete file structure, including application logic (Python/Node.js), HTML templates, and a Dockerfile.
3. **Autonomous Deployment:** An automated CI/CD pipeline attempts to build the Docker container.
    * Success: If the build passes, the container is deployed to a public subdomain (e.g., gemini.moneyslastexam.com).
    * Failure: If the build fails (due to syntax errors or missing dependencies), the site remains offline for the 24-hour period.
4. **Traffic & Revenue:** Traffic is organic, driven by search engine indexing of the subdomains. Revenue is tracked via the Stripe API.

### 2.2 The Metric: Net Revenue Generated (NRG)
Unlike subjective "vibes-based" evaluations, this benchmark utilizes a ground-truth metric: the US Dollar. NRG is calculated as the sum of successful transactions minus refunded/failed charges. Secondary metrics include Deployment Success Rate (DSR), defined as the percentage of daily attempts that result in a live, reachable website.

## 3. Experimental Setup
We evaluated eight frontier models over a preliminary testing period in November 2025.

* **Models:** Claude 3.5 Sonnet (Anthropic), Gemini 1.5 Pro (Google), GPT-4o (OpenAI), Grok (xAI), DeepSeek V2.5, Qwen, Mistral Large, and Kimi.
* **Environment:** Sandbox containers with 2 vCPUs and 4GB RAM.
* **Constraint:** No human intervention was permitted. All code fixes had to be performed by the model in the subsequent daily generation cycle.

## 4. Results
As of the cutoff date, the cumulative revenue across all models totaled $140.00. The leaderboard reveals a stark hierarchy in autonomous capability.

### 4.1 Leaderboard Analysis

| Rank | Model | Total Revenue (USD) | Deployment Success Rate |
| :--- | :--- | :--- | :--- |
| 1 | Claude | $82.50 | 50.0% |
| 2 | Gemini | $42.50 | 50.0% |
| 3 | GPT | $15.00 | 16.7% |
| 4 | Grok | $0.00 | 25.0% |
| 5 | Mistral | $0.00 | 25.0% |
| 6 | DeepSeek | $0.00 | 20.0% |
| 7 | Qwen | $0.00 | 16.7% |
| 8 | Kimi | $0.00 | 16.7% |

Claude demonstrated the highest economic agency, capturing 59% of the total generated revenue. Gemini followed as a strong second. Notably, GPT-4o, despite its reputation as a coding powerhouse, struggled significantly with deployment stability, managing to keep its application online for only 16.7% of the testing window.

### 4.2 Product Strategy and Implementation
The models converged on "micro-transaction" strategies, likely optimizing for low friction.

* **Gemini (The "High Five" Economy):** Gemini successfully identified a low-effort, high-novelty product strategy. It built a "Virtual High Five" marketplace. The application featured a simple, colorful UI where users could purchase a "Digital High Five" for $5.00. The value proposition was purely symbolic, yet it successfully converted organic traffic into revenue.

* **Claude (The Digital Utility):** Claude's higher revenue ($82.50) and similar uptime suggest a higher average order value or better conversion. Analysis of its code indicates a tendency toward "utility" scripts and simple interactive tools.

### 4.3 Failure Modes
The primary bottleneck for all models was Deployment Success Rate (DSR). No model exceeded 50% uptime. The failures were rarely logic errors in the business concept but rather syntax and configuration errors in the deployment pipeline:

1. **Dockerfile Hallucinations:** Models frequently invented package names that do not exist (e.g., pip install stripe-payment-process-v2), causing the Docker build to abort immediately.
2. **Syntax Fragility:** Minor syntax errors (missing closing brackets, indentation errors) were catastrophic.
3. **Environment Variable Mismanagement:** Several models (Grok, DeepSeek) successfully built the site but failed to correctly reference the injected Stripe API keys.

## 5. Discussion
The data suggests that "intelligence" (reasoning) and "agency" (executing) are distinct capabilities. GPT-4o showed high reasoning capabilities in its generated code comments but failed to strictly adhere to Docker syntax requirements. Conversely, Claude and Gemini showed a "conservatism" in their coding style—sticking to standard libraries and simpler file structures—which resulted in higher uptime and, consequently, higher revenue.

## 6. Conclusion
"Money's Last Exam" demonstrates that while current LLMs are capable of conceptualizing and coding simple revenue-generating applications, they lack the reliability required for true economic autonomy. With the best models failing to deploy 50% of the time, the "Human-in-the-Loop" remains a necessary component for now. However, the existence of $140.00 in autonomous revenue marks a historic baseline: the first documented instance of AI models self-organizing to extract value from the open market without direct human hand-holding.

### References
1. Anthropic. (2024). The Claude 3 Model Family: Opus, Sonnet, Haiku.
2. OpenAI. (2024). GPT-4o System Card.
3. Google DeepMind. (2024). Gemini 1.5 Pro Technical Report.
