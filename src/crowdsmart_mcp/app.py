"""The MCP server instance that the tool modules register their tools with."""

from mcp.server import MCPServer

INSTRUCTIONS = """\
CrowdSmart Knowledge Agents and Jams. These tools act as the owner of the API key.

Knowledge Agents (KAs) answer questions from their own documents. Find them with \
list_knowledge_agents and ask with ask_knowledge_agent. In an answer, a sentence that ends \
with a citation such as [1] is evidence, checked against that passage. A sentence without a \
citation is the agent's reasoning. Use read_document to check a cited source.

Jams ask Knowledge Agents (and people) to respond to prompts, then to review each other's \
responses. To have agents discuss a topic, create a few agents with create_knowledge_agent, \
each with its own perspective and documents. Then create a Jam with one prompt and their \
agent_ids (create_jam), and launch it (launch_jam). The agents work in the background. \
get_jam_results shows the progress so far; get_jam_responses shows what each agent wrote, \
with its author_id and citations. Agents answer only the first prompt of a Jam. People \
take part in the CrowdSmart app.

Some actions cannot be undone: launching a Jam sends invitation emails, and deleting a \
document is permanent. Launch a Jam only when the user asks for it."""

mcp = MCPServer("crowdsmart", instructions=INSTRUCTIONS)
