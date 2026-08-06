// TODOBA Trusted Agent
// Mission Acknowledgement Upgrade

#property strict


#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionValidator.mqh>
#include <TODOBAExecution/ExecutionPermissionGuard.mqh>
#include <TODOBAExecution/ExecutionMissionState.mqh>
#include <TODOBAExecution/ExecutionEngine.mqh>
#include <TODOBAExecution/ExecutionResult.mqh>


#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "1.4.0"


input int PollIntervalSeconds = 5;
input string CloudBaseUrl = "http://127.0.0.1:8000";
input string AgentId = "trusted-agent-001";
input string AgentSecret = "";


TODOBAExecutionMissionState current_mission_state;

TODOBAExecutionEngine execution_engine;



string BuildAuthenticationHeaders(
   const bool include_content_type
)
{
   string headers =
      "X-TODOBA-Agent-ID: "
      + AgentId
      + "\r\n"
      + "Authorization: Bearer "
      + AgentSecret
      + "\r\n";


   if(include_content_type)
   {
      headers +=
         "Content-Type: application/json\r\n";
   }


   return headers;
}



void SendAcknowledgement(
   TODOBAExecutionMission &mission
)
{
   string url =
      CloudBaseUrl + "/missions/acknowledge";


   string payload =
      "{"
      "\"mission_id\":\"" + mission.mission_id + "\","
      "\"agent_id\":\"" + mission.agent_id + "\","
      "\"sequence\":" + IntegerToString(
         mission.sequence
      ) + ","
      "\"status\":\"ACCEPTED\","
      "\"acknowledged_at\":\"2026-08-06T00:00:00Z\""
      "}";


   char request_body[];

   StringToCharArray(
      payload,
      request_body
   );


   char response_body[];

   string response_headers;


   WebRequest(
      "POST",
      url,
      BuildAuthenticationHeaders(
         true
      ),
      3000,
      request_body,
      response_body,
      response_headers
   );
}



void SendExecutionStarted(
   TODOBAExecutionMission &mission
)
{
   string url =
      CloudBaseUrl + "/missions/execution_started";


   string payload =
      "{"
      "\"mission_id\":\"" + mission.mission_id + "\","
      "\"agent_id\":\"" + mission.agent_id + "\","
      "\"sequence\":" + IntegerToString(
         mission.sequence
      ) + ","
      "\"started_at\":\"2026-08-05T00:00:00Z\""
      "}";


   char request_body[];

   StringToCharArray(
      payload,
      request_body
   );


   char response_body[];

   string response_headers;


   WebRequest(
      "POST",
      url,
      BuildAuthenticationHeaders(
         true
      ),
      3000,
      request_body,
      response_body,
      response_headers
   );
}



void SendCompleted(
   TODOBAExecutionMission &mission
)
{
   string url =
      CloudBaseUrl + "/missions/completed";


   string payload =
      "{"
      "\"mission_id\":\"" + mission.mission_id + "\","
      "\"agent_id\":\"" + mission.agent_id + "\","
      "\"sequence\":" + IntegerToString(
         mission.sequence
      ) + ","
      "\"completed_at\":\"2026-08-02T00:05:00\""
      "}";


   char request_body[];

   StringToCharArray(
      payload,
      request_body
   );


   char response_body[];

   string response_headers;


   WebRequest(
      "POST",
      url,
      BuildAuthenticationHeaders(
         true
      ),
      3000,
      request_body,
      response_body,
      response_headers
   );


   current_mission_state.Complete();
}



void SendFailed(
   TODOBAExecutionMission &mission,
   string reason
)
{
   string url =
      CloudBaseUrl + "/missions/failed";


   string payload =
      "{"
      "\"mission_id\":\"" + mission.mission_id + "\","
      "\"agent_id\":\"" + mission.agent_id + "\","
      "\"sequence\":" + IntegerToString(
         mission.sequence
      ) + ","
      "\"failed_at\":\"2026-08-02T00:05:00\","
      "\"failure_reason\":\"" + reason + "\""
      "}";


   char request_body[];

   StringToCharArray(
      payload,
      request_body
   );


   char response_body[];

   string response_headers;


   WebRequest(
      "POST",
      url,
      BuildAuthenticationHeaders(
         true
      ),
      3000,
      request_body,
      response_body,
      response_headers
   );


   current_mission_state.Fail();
}



void SendBrokerEvidence(
   TODOBAExecutionMission &mission,
   TODOBAExecutionResult &result
)
{
   string url =
      CloudBaseUrl + "/broker/evidence";


   string payload =
      "{"
      "\"mission_id\":\"" + mission.mission_id + "\","
      "\"agent_id\":\"" + mission.agent_id + "\","
      "\"success\":" + (
         result.success
         ? "true"
         : "false"
      ) + ","
      "\"retcode\":" + IntegerToString(
         result.retcode
      ) + ","
      "\"order_ticket\":" + IntegerToString(
         result.order_ticket
      ) + ","
      "\"deal_ticket\":" + IntegerToString(
         result.deal_ticket
      ) + ","
      "\"execution_price\":" + DoubleToString(
         result.price,
         2
      ) + ","
      "\"comment\":\"" + result.comment + "\","
      "\"completed_at\":\"2026-08-04T00:00:00Z\""
      "}";


   char request_body[];

   StringToCharArray(
      payload,
      request_body
   );


   char response_body[];

   string response_headers;


   WebRequest(
      "POST",
      url,
      BuildAuthenticationHeaders(
         true
      ),
      3000,
      request_body,
      response_body,
      response_headers
   );
}



void PollCloud()
{
   string url =
      CloudBaseUrl
      + "/missions/next";


   char request_body[];

   char response_body[];

   string response_headers;


   long status_code = WebRequest(
      "GET",
      url,
      BuildAuthenticationHeaders(
         false
      ),
      3000,
      request_body,
      response_body,
      response_headers
   );


   if(status_code != 200)
      return;


   string response =
      CharArrayToString(
         response_body
      );


   TODOBAExecutionMission mission;


   if(
      !TODOBAExecutionMissionParser::Parse(
         response,
         mission
      )
   )
      return;


   if(
      !TODOBAExecutionMissionValidator::Validate(
         mission,
         AgentId
      )
   )
      return;


   if(
      !TODOBAExecutionPermissionGuard::Allow(
         mission.sequence
      )
   )
      return;


   current_mission_state.Initialize(
      mission.mission_id,
      mission.agent_id,
      mission.sequence
   );


   SendAcknowledgement(
      mission
   );


   current_mission_state.Start();


   SendExecutionStarted(
      mission
   );


   Print(
      "TODOBA RECEIVED SYMBOL=[",
      mission.symbol,
      "]"
   );


   TODOBAExecutionResult execution_result =
      execution_engine.Execute(
         mission.symbol,
         mission.order_type,
         mission.volume,
         mission.entry,
         mission.sl,
         mission.tp,
         mission.magic_number,
         mission.comment
      );


   Print(
      "TODOBA Execution Result: success=",
      execution_result.success,
      " retcode=",
      execution_result.retcode,
      " order=",
      execution_result.order_ticket,
      " deal=",
      execution_result.deal_ticket,
      " price=",
      execution_result.price,
      " comment=",
      execution_result.comment
   );


   if(
      execution_result.success
   )
   {
      SendBrokerEvidence(
         mission,
         execution_result
      );

      SendCompleted(
         mission
      );
   }
   else
   {
      SendFailed(
         mission,
         execution_result.comment
      );
   }


   Print(
      TODOBA_AGENT_NAME,
      " finished mission=",
      mission.mission_id
   );
}



int OnInit()
{
   if(PollIntervalSeconds < 1)
      return INIT_PARAMETERS_INCORRECT;


   if(StringLen(CloudBaseUrl) == 0)
      return INIT_PARAMETERS_INCORRECT;


   if(StringLen(AgentId) == 0)
      return INIT_PARAMETERS_INCORRECT;


   if(StringLen(AgentSecret) == 0)
      return INIT_PARAMETERS_INCORRECT;


   EventSetTimer(
      PollIntervalSeconds
   );


   Print(
      TODOBA_AGENT_NAME,
      " v",
      TODOBA_AGENT_VERSION,
      " initialized."
   );


   return INIT_SUCCEEDED;
}



void OnDeinit(
   const int reason
)
{
   EventKillTimer();
}



void OnTimer()
{
   PollCloud();
}