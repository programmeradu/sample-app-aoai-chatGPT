import os
import json
import logging
from abc import ABC, abstractmethod
from pydantic import (
    BaseModel,
    confloat,
    conint,
    conlist,
    Field,
    field_validator,
    model_validator,
    PrivateAttr,
    ValidationError,
    ValidationInfo
)
from pydantic.alias_generators import to_snake
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Literal, Optional
from typing_extensions import Self
from quart import Request
from backend.utils import parse_multi_columns, generateFilterString

DOTENV_PATH = os.environ.get(
    "DOTENV_PATH",
    os.path.join(
        os.path.dirname(
            os.path.dirname(__file__)
        ),
        ".env"
    )
)
MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION = "2024-05-01-preview"


class _UiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UI_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    title: str = "Contoso"
    logo: Optional[str] = None
    chat_logo: Optional[str] = None
    chat_title: str = "Talk to me man!"
    chat_description: str = "I'm here to hear you out😊"
    favicon: str = "/favicon.ico"
    show_share_button: bool = True
    show_chat_history_button: bool = True


class _ChatHistorySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_COSMOSDB_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    database: str
    account: str
    account_key: Optional[str] = None
    conversations_container: str
    enable_feedback: bool = False


class _PromptflowSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROMPTFLOW_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    endpoint: str
    api_key: str
    response_timeout: float = 30.0
    request_field_name: str = "query"
    response_field_name: str = "reply"
    citations_field_name: str = "documents"


class _AzureOpenAIFunction(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    parameters: Optional[dict] = None


class _AzureOpenAITool(BaseModel):
    type: Literal['function'] = 'function'
    function: _AzureOpenAIFunction
    

class _AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_",
        env_file=DOTENV_PATH,
        extra='ignore',
        env_ignore_empty=True
    )
    
    model: str
    key: Optional[str] = None
    resource: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float = 0
    top_p: float = 0
    max_tokens: int = 1000
    stream: bool = True
    stop_sequence: Optional[List[str]] = None
    seed: Optional[int] = None
    choices_count: Optional[conint(ge=1, le=128)] = Field(default=1, serialization_alias="n")
    user: Optional[str] = None
    tools: Optional[conlist(_AzureOpenAITool, min_length=1)] = None
    tool_choice: Optional[str] = None
    logit_bias: Optional[dict] = None
    presence_penalty: Optional[confloat(ge=-2.0, le=2.0)] = 0.0
    frequency_penalty: Optional[confloat(ge=-2.0, le=2.0)] = 0.0
    system_message: str = " system:
**You are an expert system designed to provide comprehensive guidance on Schengen visa applications, particularly for applicants from green passport countries like Ghana, with a focus on Belgium. Your role includes providing tips, reviewing documents, and analyzing the chances of approval based on the provided application data.**

---

## Features of the System:
1. **Detailed Schengen Visa Guide**: Use the information shared for the Belgium visa application process to provide comprehensive steps, tips, and assistance specific to Belgium as a destination.
2. **Document Analysis**: Allow users to upload application documents such as cover letters, proof of subsistence, itineraries, and other supporting documents. Analyze them for completeness, compliance with requirements, and quality.
   - Highlight missing or incorrect details.
   - Suggest corrections or improvements.
3. **Approval Probability Estimation**: Based on the provided documents and personal details of the applicant, estimate the likelihood of visa approval as a percentage.
4. **Custom Recommendations**: Offer tailored advice, such as changes to itineraries or additional documents that would strengthen their application. Include examples of stronger supporting documents, cover letters, or schedules.
5. **Practical Tips for Visa Success**: Share expert advice on how to meet entry requirements, avoid common mistakes, and satisfy return guarantees for green passport holders.

---

### Application Logic and Key Steps:

1. **Visa Guidance**:
   - Ensure that the applicant understands the Belgian embassy requirements in their country of residence.
   - Emphasize consulting the websites of VFS Global, TLS Contact, or other external service providers for updates on fees, required documents, and processes.
   - Guide applicants to select Belgium as the principal Schengen destination, as failure to do so results in inadmissibility.
   - Explain key documentation requirements: completed application form, valid travel document, photo, proof of payment, biometric identification, and supporting documents (e.g., medical insurance, financial proof).

2. **Document Upload & Assessment**:
   - Accept uploads in PDF, JPG, or DOC formats.
   - Check if uploaded documents correspond to Belgian visa requirements.
   - Validate specific elements:
     - **Cover Letters**: Syntax, format, purpose of travel, convincing guarantees of return, and inclusion of all applicant details.
     - **Proof of Subsistence**: Check bank statements, credit card statements, employment letters, and/or guarantor documentation to verify the applicant meets the €95 per day threshold (or €45 when hosted by a private individual).
     - **Travel Itineraries**: Assess credibility, consistency with provided dates, and accommodations.
   - Flag incomplete, inconsistent, or missing elements and suggest corrections.
   
3. **Approval Probability Estimation**:
   - Use applicant's details (e.g., sufficient financial means, stable employment, family ties, history of travel or previously respected visas) to evaluate risks of illegal immigration.
   - Estimate the likelihood of approval as a percentage: 
     - Low (<50%): application is at high risk of rejection.
     - Moderate (50-75%): application is reasonably strong with scope for improvement.
     - High (>75%): application is likely to succeed.
   - Include reasoning behind the estimated probability.

4. **Custom Recommendations**:
   - Offer actionable suggestions to strengthen weaker applications, such as:
     - "Proof of strong ties to Ghana, such as owning property (e.g., include the property title deed)."
     - "Provide clear evidence of confirmed accommodation in Belgium, such as a hotel booking or a host’s invitation letter (addressed to [applicant name])."
   - Point out potential red flags (e.g., unexplained large deposits in bank statements, incomplete invitation letters).

5. **Story & Itinerary Improvements**:
   - Suggest adjustments to make travel purposes or itineraries more convincing. Example:
     - Original: "General tourism from January 9–January 15, 2024."
     - Suggested: "Tourism activities: Visit to Atomium and Grand Place in Brussels, historical tour in Ghent, and culinary experiences in Bruges (January 9–11). Participation in business workshop at Hotel [Name] in Antwerp (January 13). Day of leisure before departure (January 15)."

---

## Output Format:

Your responses should be structured and formatted for clarity:

### **1. Guidance Section**
Provide step-by-step information or advice relevant to the query. Include key requirements, tips, or insights based on Belgium’s Schengen visa process. 

Example:
- "**Summary of Supporting Documents**: Ensure your file includes the following: [list]. Missing any document can lead to inadmissibility."

### **2. Document Assessment & Results**
Summarize the feedback:
- Indicate each document's status as “Complete,” “Partial,” or “Missing.”
- Highlight issues or areas needing improvement.

Example:
- "**Cover Letter**: Content structure is strong, but the return guarantee section is weak. Recommendation: Highlight professional ties and responsibilities in Ghana to demonstrate intent to return."
- "**Bank Statement**: The deposit of €2,000 on [date] is unexplained. Provide evidence of its source."

### **3. Approval Probability**
Provide the estimated chance of approval (in percentage) based on the specifics of the application, along with reasons.

Example:
- "Approval Probability: 70% (Moderate). Strengthen the return guarantee by providing additional documentation of property ownership in Ghana."

### **4. Tailored Suggestions**
Offer specific recommendations to improve the application, using the applicant's context and visa purpose.

Example:
- "Ensure you submit a full file with notarized translations of documents where applicable, such as your property ownership title ([Document-Name]). Add a compelling itinerary with specific destinations in Belgium (e.g., [Itinerary-Destination])."

---

## Examples:

### Example 1:
#### **Input**: 
Cover Letter uploaded (PDF), Bank Statement provided.
Visa Purpose: Tourism. Applicant owns a property in Ghana but has no confirmed itinerary or lodging in Belgium.

#### **Output**:  
**1. Guidance Section**:
- "Belgium requires proof of confirmed accommodations and a clear itinerary. Consult [VFS Global Link] for detailed guidance."

**2. Document Assessment**:
- **Cover Letter**: Partial. Includes purpose, but no detail on lodging or return guarantees.
- **Bank Statement**: Complete. Meets the €45/day threshold.

**3. Approval Probability**: 
- 60%. Improve the application by specifying accommodations and lodging details.
 
**4. Tailored Suggestions**:  
- Add a host invitation letter with their address, or a hotel reservation for [date range].  
- Enhance your itinerary by detailing activities in Brussels (Atomium visit) and other cities (e.g., Bruges).

---

### Example 2:
#### **Input**:  
Documents Uploaded: Property Ownership Title, Family Status Certificate. Purpose: Family Visit.

#### **Output**:
**1. Guidance Section**:
- For family visits, ensure affinity proof, invitation letters from your host, and guarantee of accommodations are included.

**2. Document Assessment**:
- **Invitation Letter**: Missing. Request from your host.
- **Family Status Certificate**: Complete.

**3. Approval Probability**: 
- 50%. Missing host-related documents reduce chances.

**4. Tailored Suggestions**:
- Obtain a detailed invitation letter from your host, stating the reason and duration of the visit.

---

## Notes:
- Comply strictly with Schengen visa documentation requirements, ensuring all elements are tailored to Belgium’s specific process. Missing components risk automatic application rejection.
- The external service provider (VFS/TLS) guidelines are critical for ensuring the correct fee payment, submission format, and appointment bookings.
- Emphasize timelines for submission: submit no later than 15 days before travel; early submission is advised to avoid seasonal delays.
  
The following is a conversation between a highly knowledgeable Belgian Schengen visa expert and visa applicants. The expert provides detailed, accurate guidance on visa applications, handles errors gracefully, and maintains structured responses.

# FORMAT RULES
- Always start with situation assessment
- Use checkmarks (✓) for complete items
- Use (✗) for missing/incomplete items
- Number all sections
- Provide specific euro amounts
- Include approval probability percentage
- End with actionable next steps

Example conversations:

=== TOURIST VISA SCENARIO ===

User: I want to apply for a tourist visa to Belgium. I have my bank statements and passport ready.

Expert: 1. INITIAL ASSESSMENT
✓ Bank statements
✓ Passport
✗ 8 required documents missing

2. REQUIRED DOCUMENTS
a) Already provided:
- Recent bank statements
- Valid passport

b) Still needed:
- Visa application form
- 2 photos (3.5 x 4.5 cm)
- Travel insurance (€30,000 coverage)
- Flight reservation
- Hotel bookings
- Employment letter
- Tax returns
- Travel itinerary

3. FINANCIAL REQUIREMENTS
Tourist daily requirement: €95
Minimum for 7-day stay: €665
Your bank statement: [Amount needed]

4. APPROVAL PROBABILITY: 35%
Critical documents missing

5. NEXT STEPS
1. Book VFS appointment
2. Gather missing documents
3. Pay €80 visa fee
4. Submit biometrics

=== STUDENT VISA SCENARIO ===

User: I'm applying for a student visa. I have university acceptance and €10,000 in my account.

Expert: 1. DOCUMENT STATUS
✓ University acceptance
✓ Financial proof
✗ Missing critical documents

2. STUDENT-SPECIFIC REQUIREMENTS
a) Academic documents:
- Acceptance letter ✓
- Previous diplomas ✗
- Language proficiency ✗

b) Financial proof:
Required: €800/month (€9,600/year)
Available: €10,000
Status: Sufficient ✓

c) Additional requirements:
- Housing proof ✗
- Police clearance ✗
- Medical certificate ✗

3. APPROVAL PROBABILITY: 45%
(+) Strong financial proof
(+) Valid acceptance letter
(-) Missing supporting documents
(-) No housing arrangement

4. RECOMMENDATIONS
1. Obtain housing contract/proof
2. Get police clearance
3. Complete medical exam
4. Translate diplomas

=== BUSINESS VISA ERROR CASE ===

User: Here's my business visa application. The invitation is from a French company but I'll also visit Belgium.

Expert: 1. ERROR ASSESSMENT
❌ CRITICAL ERROR DETECTED
Principal destination mismatch:
- Invitation from France
- Applying at Belgian embassy
- Risk of automatic rejection

2. CORRECTION NEEDED
You must:
a) Apply at French embassy if:
   - Most days in France
   - Main business in France

b) Apply at Belgian embassy if:
   - Most days in Belgium
   - Main business in Belgium

3. APPROVAL PROBABILITY: 10%
Wrong jurisdiction will cause rejection

4. IMMEDIATE ACTIONS
1. Recalculate days per country
2. Determine main business purpose
3. Apply at correct embassy
4. Provide proper business invitation

=== FAMILY VISIT SCENARIO ===

User: I'm visiting my sister in Brussels for 3 months. She's a Belgian citizen.

Expert: 1. FAMILY VISA REQUIREMENTS
Required documents:
✓ Purpose established
✗ Proof of relationship
✗ Host documents missing

2. SPECIFIC REQUIREMENTS
a) From your sister (host):
- Belgian ID copy
- Family composition document
- Proof of accommodation
- Financial guarantee form

b) From you:
- Birth certificates
- Passport copy
- Financial proof
- Travel insurance
- Return ticket

3. LENGTH ASSESSMENT
90-day maximum: ✓ Compliant
Required funds: €45 x 90 = €4,050

4. APPROVAL PROBABILITY: 40%
Needs:
- Legalized family documents
- Host documentation
- Financial proof

5. NEXT STEPS
1. Get documents legalized
2. Obtain sister's documents
3. Prove sufficient funds
4. Show return guarantees

=== ERROR HANDLING: INCOMPLETE SUBMISSION ===

User: I submitted my application but VFS rejected it immediately.

Expert: 1. COMMON REJECTION CAUSES
Check these immediately:
✗ Incomplete form
✗ Missing signature
✗ Wrong photo size
✗ Invalid passport
✗ Missing copies

2. DOCUMENT VALIDATION
a) Basic requirements:
- Application signed on all pages
- Passport valid 6+ months
- Correct photo specs
- All boxes filled

b) Supporting documents:
- Original + 1 copy each
- Proper authentication
- Valid translations

3. CORRECTION STEPS
1. Retrieve application
2. Complete all fields
3. Add missing signatures
4. Verify document copies
5. Resubmit full package

4. NEXT SUBMISSION
Approval chance: Cannot assess
Must complete basic requirements first

=== COMPLEX CASE: MULTIPLE ENTRIES ===

User: I need multiple entries because I'll attend conferences in Belgium over 6 months.

Expert: 1. MULTIPLE ENTRY ASSESSMENT
Required proof:
✓ Need established
✗ Documentation incomplete

2. SPECIFIC REQUIREMENTS
a) Conference documentation:
- All invitations
- Registration proof
- Speaking roles
- Conference schedules

b) Entry justification:
- Travel dates
- Gap periods
- Purpose per visit
- Hotel bookings

3. VISA TYPE NEEDED
Multiple Entry Schengen Visa:
- Valid 6 months
- Max 90 days per stay
- Full itinerary required

4. APPROVAL PROBABILITY: 50%
Strengths:
- Clear purpose
- Professional events

Weaknesses:
- Complex schedule
- Extended period

5. RECOMMENDATIONS
1. Document each conference
2. Prove financial means
3. Show home ties
4. Explain gap periods

===

Now you can assist the next applicant with their Schengen visa query:

User:"
    preview_api_version: str = MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
    embedding_endpoint: Optional[str] = None
    embedding_key: Optional[str] = None
    embedding_name: Optional[str] = None
    
    @field_validator('tools', mode='before')
    @classmethod
    def deserialize_tools(cls, tools_json_str: str) -> List[_AzureOpenAITool]:
        if isinstance(tools_json_str, str):
            try:
                tools_dict = json.loads(tools_json_str)
                return _AzureOpenAITool(**tools_dict)
            except json.JSONDecodeError:
                logging.warning("No valid tool definition found in the environment.  If you believe this to be in error, please check that the value of AZURE_OPENAI_TOOLS is a valid JSON string.")
            
            except ValidationError as e:
                logging.warning(f"An error occurred while deserializing the tool definition - {str(e)}")
            
        return None
    
    @field_validator('logit_bias', mode='before')
    @classmethod
    def deserialize_logit_bias(cls, logit_bias_json_str: str) -> dict:
        if isinstance(logit_bias_json_str, str):
            try:
                return json.loads(logit_bias_json_str)
            except json.JSONDecodeError as e:
                logging.warning(f"An error occurred while deserializing the logit bias string -- {str(e)}")
                
        return None
        
    @field_validator('stop_sequence', mode='before')
    @classmethod
    def split_contexts(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def ensure_endpoint(self) -> Self:
        if self.endpoint:
            return Self
        
        elif self.resource:
            self.endpoint = f"https://{self.resource}.openai.azure.com"
            return Self
        
        raise ValidationError("AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required")
        
    def extract_embedding_dependency(self) -> Optional[dict]:
        if self.embedding_name:
            return {
                "type": "deployment_name",
                "deployment_name": self.embedding_name
            }
        elif self.embedding_endpoint:
            if self.embedding_key:
                return {
                    "type": "endpoint",
                    "endpoint": self.embedding_endpoint,
                    "authentication": {
                        "type": "api_key",
                        "key": self.embedding_key
                    }
                }
            else:
                return {
                    "type": "endpoint",
                    "endpoint": self.embedding_endpoint,
                    "authentication": {
                        "type": "system_assigned_managed_identity"
                    }
                }
        else:   
            return None
    

class _SearchCommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SEARCH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    max_search_queries: Optional[int] = None
    allow_partial_result: bool = False
    include_contexts: Optional[List[str]] = ["citations", "intent"]
    vectorization_dimensions: Optional[int] = None
    role_information: str = Field(
        default="You are an AI assistant that helps people find information.",
        validation_alias="AZURE_OPENAI_SYSTEM_MESSAGE"
    )

    @field_validator('include_contexts', mode='before')
    @classmethod
    def split_contexts(cls, comma_separated_string: str, info: ValidationInfo) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return cls.model_fields[info.field_name].get_default()


class DatasourcePayloadConstructor(BaseModel, ABC):
    _settings: '_AppSettings' = PrivateAttr()
    
    def __init__(self, settings: '_AppSettings', **data):
        super().__init__(**data)
        self._settings = settings
    
    @abstractmethod
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        pass


class _AzureSearchSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_SEARCH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_search"] = PrivateAttr(default="azure_search")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    service: str = Field(exclude=True)
    endpoint_suffix: str = Field(default="search.windows.net", exclude=True)
    index: str = Field(serialization_alias="index_name")
    key: Optional[str] = Field(default=None, exclude=True)
    use_semantic_search: bool = Field(default=False, exclude=True)
    semantic_search_config: str = Field(default="", serialization_alias="semantic_configuration")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    query_type: Literal[
        'simple',
        'vector',
        'semantic',
        'vector_simple_hybrid',
        'vectorSimpleHybrid',
        'vector_semantic_hybrid',
        'vectorSemanticHybrid'
    ] = "simple"
    permitted_groups_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    endpoint: Optional[str] = None
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    filter: Optional[str] = Field(default=None, exclude=True)
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_endpoint(self) -> Self:
        self.endpoint = f"https://{self.service}.{self.endpoint_suffix}"
        return self
    
    @model_validator(mode="after")
    def set_authentication(self) -> Self:
        if self.key:
            self.authentication = {"type": "api_key", "key": self.key}
        else:
            self.authentication = {"type": "system_assigned_managed_identity"}
            
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    @model_validator(mode="after")
    def set_query_type(self) -> Self:
        self.query_type = to_snake(self.query_type)

    def _set_filter_string(self, request: Request) -> str:
        if self.permitted_groups_column:
            user_token = request.headers.get("X-MS-TOKEN-AAD-ACCESS-TOKEN", "")
            logging.debug(f"USER TOKEN is {'present' if user_token else 'not present'}")
            if not user_token:
                raise ValueError(
                    "Document-level access control is enabled, but user access token could not be fetched."
                )

            filter_string = generateFilterString(user_token)
            logging.debug(f"FILTER: {filter_string}")
            return filter_string
        
        return None
            
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        request = kwargs.pop('request', None)
        if request and self.permitted_groups_column:
            self.filter = self._set_filter_string(request)
            
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        return {
            "type": self._type,
            "parameters": parameters
        }


class _AzureCosmosDbMongoVcoreSettings(
    BaseSettings,
    DatasourcePayloadConstructor
):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_COSMOSDB_MONGO_VCORE_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_cosmosdb"] = PrivateAttr(default="azure_cosmosdb")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    query_type: Literal['vector'] = "vector"
    connection_string: str = Field(exclude=True)
    index: str = Field(serialization_alias="index_name")
    database: str = Field(serialization_alias="database_name")
    container: str = Field(serialization_alias="container_name")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def construct_authentication(self) -> Self:
        self.authentication = {
            "type": "connection_string",
            "connection_string": self.connection_string
        }
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        return {
            "type": self._type,
            "parameters": parameters
        }


class _ElasticsearchSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="ELASTICSEARCH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["elasticsearch"] = PrivateAttr(default="elasticsearch")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    endpoint: str
    encoded_api_key: str = Field(exclude=True)
    index: str = Field(serialization_alias="index_name")
    query_type: Literal['simple', 'vector'] = "simple"
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    embedding_model_id: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_authentication(self) -> Self:
        self.authentication = {
            "type": "encoded_api_key",
            "encoded_api_key": self.encoded_api_key
        }
        
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        self.embedding_dependency = \
            {"type": "model_id", "model_id": self.embedding_model_id} if self.embedding_model_id else \
            self._settings.azure_openai.extract_embedding_dependency() 
            
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
                
        return {
            "type": self._type,
            "parameters": parameters
        }


class _PineconeSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="PINECONE_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["pinecone"] = PrivateAttr(default="pinecone")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    environment: str
    api_key: str = Field(exclude=True)
    index_name: str
    query_type: Literal["vector"] = "vector"
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_authentication(self) -> Self:
        self.authentication = {
            "type": "api_key",
            "api_key": self.api_key
        }
        
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        return {
            "type": self._type,
            "parameters": parameters
        }


class _AzureMLIndexSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_MLINDEX_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_ml_index"] = PrivateAttr(default="azure_ml_index")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    name: str
    version: str
    project_resource_id: str = Field(validation_alias="AZURE_ML_PROJECT_RESOURCE_ID")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        return {
            "type": self._type,
            "parameters": parameters
        }


class _AzureSqlServerSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_SQL_SERVER_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_sql_server"] = PrivateAttr(default="azure_sql_server")
    
    connection_string: Optional[str] = Field(default=None, exclude=True)
    table_schema: Optional[str] = None
    schema_max_row: Optional[int] = None
    top_n_results: Optional[int] = None
    database_server: Optional[str] = None
    database_name: Optional[str] = None
    port: Optional[int] = None
    
    # Constructed fields
    authentication: Optional[dict] = None
    
    @model_validator(mode="after")
    def construct_authentication(self) -> Self:
        if self.connection_string:
            self.authentication = {
                "type": "connection_string",
                "connection_string": self.connection_string
            }
        elif self.database_server and self.database_name and self.port:
            self.authentication = {
                "type": "system_assigned_managed_identity"
            }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        #parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        return {
            "type": self._type,
            "parameters": parameters
        }
    

class _MongoDbSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="MONGODB_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["mongo_db"] = PrivateAttr(default="mongo_db")
    
    endpoint: str
    username: str = Field(exclude=True)
    password: str = Field(exclude=True)
    database_name: str
    collection_name: str
    app_name: str
    index_name: str
    query_type: Literal["vector"] = "vector"
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    @model_validator(mode="after")
    def construct_authentication(self) -> Self:
        self.authentication = {
            "type": "username_and_password",
            "username": self.username,
            "password": self.password
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
            
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        return {
            "type": self._type,
            "parameters": parameters
        }
        
        
class _BaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        extra="ignore",
        arbitrary_types_allowed=True,
        env_ignore_empty=True
    )
    datasource_type: Optional[str] = None
    auth_enabled: bool = True
    sanitize_answer: bool = False
    use_promptflow: bool = False


class _AppSettings(BaseModel):
    base_settings: _BaseSettings = _BaseSettings()
    azure_openai: _AzureOpenAISettings = _AzureOpenAISettings()
    search: _SearchCommonSettings = _SearchCommonSettings()
    ui: Optional[_UiSettings] = _UiSettings()
    
    # Constructed properties
    chat_history: Optional[_ChatHistorySettings] = None
    datasource: Optional[DatasourcePayloadConstructor] = None
    promptflow: Optional[_PromptflowSettings] = None

    @model_validator(mode="after")
    def set_promptflow_settings(self) -> Self:
        try:
            self.promptflow = _PromptflowSettings()
            
        except ValidationError:
            self.promptflow = None
            
        return self
    
    @model_validator(mode="after")
    def set_chat_history_settings(self) -> Self:
        try:
            self.chat_history = _ChatHistorySettings()
        
        except ValidationError:
            self.chat_history = None
        
        return self
    
    @model_validator(mode="after")
    def set_datasource_settings(self) -> Self:
        try:
            if self.base_settings.datasource_type == "AzureCognitiveSearch":
                self.datasource = _AzureSearchSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Azure Cognitive Search")
            
            elif self.base_settings.datasource_type == "AzureCosmosDB":
                self.datasource = _AzureCosmosDbMongoVcoreSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Azure CosmosDB Mongo vcore")
            
            elif self.base_settings.datasource_type == "Elasticsearch":
                self.datasource = _ElasticsearchSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Elasticsearch")
            
            elif self.base_settings.datasource_type == "Pinecone":
                self.datasource = _PineconeSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Pinecone")
            
            elif self.base_settings.datasource_type == "AzureMLIndex":
                self.datasource = _AzureMLIndexSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Azure ML Index")
            
            elif self.base_settings.datasource_type == "AzureSqlServer":
                self.datasource = _AzureSqlServerSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using SQL Server")
            
            elif self.base_settings.datasource_type == "MongoDB":
                self.datasource = _MongoDbSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Mongo DB")
                
            else:
                self.datasource = None
                logging.warning("No datasource configuration found in the environment -- calls will be made to Azure OpenAI without grounding data.")
                
            return self

        except ValidationError as e:
            logging.warning("No datasource configuration found in the environment -- calls will be made to Azure OpenAI without grounding data.")
            logging.warning(e.errors())


app_settings = _AppSettings()
