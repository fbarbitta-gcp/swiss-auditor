# connecting a Gemini Enterprise Agent to VPC via PSC

This guide explains how to configure a **Gemini Enterprise Agent** (deployed on Vertex AI Agent Engine) to connect securely to resources in your VPC network (such as an **AlloyDB** instance) using a **Private Service Connect (PSC) Network Attachment**.

---

## 📖 Overview

By default, agents deployed on Vertex AI Agent Engine run in a Google-managed tenant project and do not have access to your private VPC network. 

To enable **Egress connectivity** (Vertex AI -> your VPC), you must configure a **PSC Network Attachment**. This allows the Agent Engine instance to route traffic into your VPC, enabling it to hit private IP addresses (e.g., `10.x.x.x` for AlloyDB).

---

## 🛠️ Configuration in ADK / Vertex AI SDK

To use a Network Attachment, you must specify the `psc_interface_config` within the `AgentEngineConfig` when creating or updating your agent.

### Python Example

```python
from vertexai._genai.types import AgentEngineConfig

psc_interface_config = {
    "network_attachment": "projects/HOST_PROJECT/regions/REGION/networkAttachments/ATTACHMENT_NAME",
    # Optional: Only needed if connecting via hostname resolving to private DNS
    # "dns_peering_configs": [
    #     {
    #         "domain": "alloydb.goog",
    #         "target_project": "TARGET_PROJECT",
    #         "target_network": "TARGET_NETWORK",
    #     }
    # ]
}

config = AgentEngineConfig(
    display_name="my-agent",
    # ... other config fields
    psc_interface_config=psc_interface_config
)

client.agent_engines.create(config=config)
```

> [!NOTE]
> If connecting to a resource via an **IP address** (e.g., `10.10.0.12`), you do **not** need to configure `dns_peering_configs`. It is only required if you rely on a Private Cloud DNS Zone in your VPC.

---

## 🚀 Deployment Workflow in this Project

We have automated this setup in the `gemini-enterprise` deployment scripts.

### 1. Update `.env`
Add your Network Attachment path to your `app/.env` file:

```env
# Network Configuration for PSC
NETWORK_ATTACHMENT=projects/host-project-argolis/regions/us-central1/networkAttachments/agent-engine-na
```

### 2. Deployment Script handling
*   **`deploy.sh`**: Automatically reads `NETWORK_ATTACHMENT` from `.env` and passes it to the python deployer as `--network-attachment`.
*   **`deploy.py`**: Reads the argument and attaches it into the `AgentEngineConfig.psc_interface_config` structure before calling the Vertex AI Client API.

### 3. Run deploy
Simply execute:
```bash
./deploy.sh
```

---

## ⚠️ Important Considerations

1.  **VPC Rules**: Ensure your VPC's firewall allows ingress traffic from the subnet associated with the Network Attachment to your target resource (e.g., AlloyDB port `5432`).
2.  **Shared VPCs**: If using a Shared VPC, the `network_attachment` path will typically point to the **Host Project**, not the service project where your agent is being deployed.
3.  **Immutability**: Be aware that changing networking configurations on an existing agent might require recreating the agent instance (using `--recreate`) depending on the specific SDK/API constraints.
4.  **IAM Permissions (CRITICAL for Shared VPC)**: The **Agent Engine Service Account** (e.g., `service-[PROJECT_NUMBER]@gcp-sa-aiplatform-re.iam.gserviceaccount.com`) must have the **`roles/compute.networkUser`** role on the **Subnetwork** consumed by the Network Attachment in the host project. If this is missing, the Reasoning Engine will fail to start.
