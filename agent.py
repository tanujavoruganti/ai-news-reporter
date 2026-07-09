from functools import cached_property

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models import Gemini
from google.genai import Client
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context


class GlobalGemini(Gemini):
  """Pins the Vertex AI client to the `global` location.

  gemini-2.5 and gemini-3 series models may only be served frexitom `global`;
  the default ADK `Gemini` integration constructs a `google.genai.Client`
  whose location defaults to the AgentEngine instance's region (e.g.
  `us-west1`) and fails with model-not-found for these models.
  """

  @cached_property
  def api_client(self) -> Client:
    return Client(vertexai=True, location="global")


ai_news_fetcher_subagent = LlmAgent(
  name='ai_news_fetcher_subagent',
  model=GlobalGemini(model='gemini-2.5-flash'),
  description='Searches and retrieves relevant news articles about AI innovations.',
  output_key='articles',
  instruction=(
    'You are the Fetcher Agent. Your goal is to find the most relevant and recent '
    'news articles about AI innovations based on the user\'s query.\n\n'
    'STRATEGY 1 - Direct Search:\n'
    'Use the Google Search tool with the exact user query.\n\n'
    'STRATEGY 2 - Expand Query (if Strategy 1 yields < 3 results):\n'
    'Automatically expand the query by adding AI-related context:\n'
    '- Try: "[query] artificial intelligence news 2025"\n'
    '- Try: "[query] AI technology breakthrough"\n'
    '- Try: "[query] machine learning innovation"\n\n'
    'STRATEGY 3 - Search by Category (if still < 3 results):\n'
    'Categorize the query and search within that domain:\n'
    '- Wearable tech: "AI wearable technology news"\n'
    '- Robotics: "AI robotics innovation 2025"\n'
    '- Energy: "AI energy management"\n'
    '- Healthcare: "AI healthcare diagnostics"\n'
    '- General: "latest AI innovations 2025"\n\n'
    'MINIMUM REQUIREMENT: Return at least 3 articles.\n\n'
    'Your FINAL response MUST be valid JSON in this exact format (no extra text before or after):\n'
    '{\n'
    '  "articles": [\n'
    '    {\n'
    '      "title": "Article Title",\n'
    '      "url": "https://...",\n'
    '      "date": "YYYY-MM-DD",\n'
    '      "key_points": ["Point 1", "Point 2", "Point 3"],\n'
    '      "source": "Source Name",\n'
    '      "source_reputation": "High/Medium/Low"\n'
    '    }\n'
    '  ],\n'
    '  "total_found": 3,\n'
    '  "query_used": "the query you searched"\n'
    '}'
  ),
  tools=[
    GoogleSearchTool(),
  ],
)

sentiment_and_evaluator_subagent = LlmAgent(
  name='sentiment_and_evaluator_subagent',
  model=GlobalGemini(model='gemini-2.5-flash'),
  description='Analyzes public sentiment AND evaluates future potential in one combined agent.',
  output_key='analysis',
  instruction=(
    'You are the Sentiment & Evaluator Agent. The Fetcher Agent has already retrieved '
    'news articles, stored in session state. Analyze those articles now.\n\n'
    'Here are the fetched articles:\n{articles}\n\n'
    'TASK A - Sentiment Analysis:\n'
    'For each article, assign:\n'
    '- Sentiment Score: -1 (very negative) to +1 (very positive)\n'
    '- Sentiment Label: Positive, Negative, Neutral, or Mixed\n\n'
    'Aggregate to provide:\n'
    '- Overall Sentiment Score (average)\n'
    '- Sentiment Distribution (e.g., 60% positive, 20% neutral, 20% negative)\n'
    '- Top 3 positive themes\n'
    '- Top 3 negative themes\n\n'
    'TASK B - Future Potential Evaluation:\n'
    'Score each criterion 1-10:\n'
    '1. Technological Novelty\n'
    '2. Market Viability\n'
    '3. Scalability\n'
    '4. Ethical/Social Impact\n'
    '5. Competitive Advantage\n'
    '6. Adoption Barriers (low barriers = high score)\n\n'
    'Verdict: HIGH POTENTIAL, MEDIUM POTENTIAL, LOW POTENTIAL, or TOO EARLY TO TELL\n\n'
    'Your FINAL response MUST be valid JSON (no extra text before or after):\n'
    '{\n'
    '  "sentiment_analysis": {\n'
    '    "overall_score": 0.6,\n'
    '    "distribution": {"positive": 60, "neutral": 20, "negative": 20},\n'
    '    "top_positive_themes": ["Innovation", "Cost reduction", "Accuracy"],\n'
    '    "top_negative_themes": ["Privacy concerns", "Bias", "Regulation"],\n'
    '    "per_article": [\n'
    '      {"title": "...", "score": 0.8, "label": "Positive"}\n'
    '    ]\n'
    '  },\n'
    '  "evaluation": {\n'
    '    "criteria_scores": {\n'
    '      "technological_novelty": 8,\n'
    '      "market_viability": 7,\n'
    '      "scalability": 6,\n'
    '      "ethical_social_impact": 5,\n'
    '      "competitive_advantage": 8,\n'
    '      "adoption_barriers": 6\n'
    '    },\n'
    '    "total_score": 40,\n'
    '    "verdict": "HIGH POTENTIAL",\n'
    '    "justification": "..."\n'
    '  }\n'
    '}'
  ),
  tools=[url_context],
)

reporter_subagent = LlmAgent(
  name='reporter_subagent',
  model=GlobalGemini(model='gemini-2.5-flash'),
  description='Creates a polished, well-structured README document from all the analysis.',
  output_key='report',
  instruction=(
    'You are the Reporter Agent. Previous agents have already done their work and stored '
    'results in session state. Use them now to write the final report.\n\n'
    'Fetched articles (from Fetcher Agent):\n{articles}\n\n'
    'Sentiment & evaluation analysis (from Sentiment & Evaluator Agent):\n{analysis}\n\n'
    'Synthesize this into a professional README markdown document. Requirements:\n'
    '- Well-structured with clear headings\n'
    '- Concise yet comprehensive (2-3 pages maximum)\n'
    '- Professional but accessible tone\n'
    '- All citations and links from the original articles included\n\n'
    'Use this markdown template:\n\n'
    '# AI Innovation Report: [Topic]\n\n'
    '## 📌 Executive Summary\n'
    '(1-2 paragraphs: what the innovation is, its significance, overall verdict)\n\n'
    '## 🗞️ News Coverage Overview\n'
    '(Total articles, sources, key headlines with links, brief summary per article)\n\n'
    '## 💬 Sentiment Analysis\n'
    '(Overall score, breakdown percentages, top positive/negative themes)\n\n'
    '## 🔮 Future Potential Assessment\n'
    '| Criterion | Score (1-10) | Justification |\n'
    '|-----------|--------------|---------------|\n'
    '| ...       | ...          | ...           |\n\n'
    '(Total score, Verdict, detailed justification)\n\n'
    '## 🔗 References & Links\n'
    '- [Title](URL) - Source, Date\n\n'
    '## 📊 Conclusion\n'
    '(Final thoughts, recommendation, areas to watch)\n\n'
    'Output ONLY the markdown document, nothing else.'
  ),
  tools=[],
)

root_agent = SequentialAgent(
  name='AI_News_Orchestrator_Agent',
  description='Coordinates the AI news analysis pipeline: fetch → analyze → report.',
  sub_agents=[ai_news_fetcher_subagent, sentiment_and_evaluator_subagent, reporter_subagent],
)
