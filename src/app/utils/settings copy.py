from dataclasses import dataclass
import os
import secrets

import psycopg2

from .secret_manager import SecretManager

@dataclass
class Settings:
    _instance = None
    #aws keys
    aws_region = os.environ.get('AWS_REGION') 
    app_secret_id= os.environ.get('APP_SECRET_ID') 
    db_secret_id= os.environ.get('DB_SECRET_ID') 

    # llm keys
    llm_type = os.environ.get('LLM_TYPE')

    # Toyota LLM keys
    toyota_llm_endpoint = None
    toyota_llm_auth_endpoint = None
    toyota_llm_client_id = None
    toyota_llm_client_secret = None
    toyota_llm_model = None

    # Azure OpenAI LLM keys
    openai_llm_model = None
    openai_endpoint = None
    openai_api_version = None
    openai_api_key = None
    llm_max_token = os.environ.get('LLM_MAX_TOKEN')
    llm_fetch_max_token = os.environ.get('LLM_FETCH_MAX_TOKEN')
    cubeassist_mcp_server_url = os.environ.get('CUBEASSIST_MCP_SERVER_URL')
    #application / agent keys
    logging_level = os.environ.get("LOGGING_LEVEL", "DEBUG")
    app_logging_level = os.environ.get("APP_LOGGING_LEVEL", "INFO")
    app_name = os.environ.get('APP_NAME') 
    env = os.environ.get('ENV','local')
    agent_db_host = os.environ.get('DB_HOST')
    agent_db_port = os.environ.get('DB_PORT') 
    agent_db_name = os.environ.get('DB_NAME')
    agent_db_user = os.environ.get('DB_USER')
    agent_db_password = os.environ.get('DB_PASSWORD')
    pipeline_token = os.environ.get("PIPELINE_TOKEN")
    a2a_server_url = os.environ.get('A2A_SERVER_URL')
    nso_agent_url = os.environ.get('NSO_AGENT_URL')
    pipeline_agent_url = os.environ.get('PIPELINE_AGENT_URL')
    vdm_agent_url = os.environ.get('VDM_AGENT_URL')
    workflow_agent_url = os.environ.get('WORKFLOW_AGENT_URL')
    #user_role="CUBE_E2E_ADMIN"

    # Database schema configurations
    workflow_schema: str = os.getenv("WORKFLOW_SCHEMA", "workflows")
    cube_assist_schema: str = os.getenv("CUBE_ASSIST_SCHEMA", "supplychain_assist")

    def __new__(self, *args, **kwargs):
        if self._instance is None:
            self._instance = super().__new__(self)
            self._instance.value = secrets.randbelow(100)
        return self._instance 

    def __init__(self):

        db_secrets = SecretManager.get_secrets(self.aws_region, self.db_secret_id)
        self.agent_db_user = db_secrets.get('username')
        self.agent_db_password = db_secrets.get('password')
        self.load_from_db()
        app_secrets = SecretManager.get_secrets(self.aws_region, self.app_secret_id)
        self.openai_api_key = app_secrets.get('OPENAI_API_KEY')
        self.toyota_llm_client_id = app_secrets.get('TOYOTA_LLM_CLIENT_ID')
        self.toyota_llm_client_secret = app_secrets.get('TOYOTA_LLM_CLIENT_SECRET')


    def load_from_db(self):
        conn = psycopg2.connect(
            host=self.agent_db_host,
            database=self.agent_db_name,
            user=self.agent_db_user,
            password=self.agent_db_password,
            port=self.agent_db_port,
        )
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT a.agent_id, acs.key, acs.value
                    FROM supplychain_assist.agent a
                    INNER JOIN supplychain_assist.agent_config_store acs
                        ON a.agent_id = acs.agent_id
                    WHERE a.name = %s
                """
                cur.execute(query, (self.app_name,))
                rows = cur.fetchall()
                for row in rows:
                    _, key, value = row
                    key_lower = key.lower()
                    if hasattr(self, key_lower):
                        setattr(self, key_lower, value)
                    else:
                        continue
                        # raise AttributeError(f"Unknown configuration key from DB: {key}")
        finally:
            conn.close()

    def reload(self):
        Settings._instance = None
SETTINGS = Settings()
