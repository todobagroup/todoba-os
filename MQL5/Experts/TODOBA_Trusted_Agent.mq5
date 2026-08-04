// TODOBA Trusted Agent
// Result contract upgrade

#property strict


#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionValidator.mqh>
#include <TODOBAExecution/ExecutionPermissionGuard.mqh>
#include <TODOBAExecution/ExecutionMissionState.mqh>
#include <TODOBAExecution/ExecutionEngine.mqh>
#include <TODOBAExecution/ExecutionResult.mqh>


#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "1.1.0"


input int PollIntervalSeconds = 5;
input string CloudBaseUrl = "http://127.0.0.1:8000";
input string AgentId = "trusted-agent-001";


TODOBAExecutionMissionState current_mission_state;

TODOBAExecutionEngine execution_engine;



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
      "Content-Type: application/json\r\n",
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
      "Content-Type: application/json\r\n",
      3000,
      request_body,
      response_body,
      response_headers
   );


   current_mission_state.Fail();
}



void PollCloud()
{
   string url =
      CloudBaseUrl
      + "/missions/next?agent_id="
      + AgentId;

   char request_body[];

   char response_body[];

   string response_headers;


   int status_code = WebRequest(
      "GET",
      url,
      "",
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


  current_mission_state.Start();


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