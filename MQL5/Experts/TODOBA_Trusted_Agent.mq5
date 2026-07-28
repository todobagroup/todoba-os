#property strict

#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionValidator.mqh>
#include <TODOBAExecution/ExecutionPermissionGuard.mqh>

#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "0.5.0"

input int PollIntervalSeconds = 5;
input string CloudBaseUrl = "http://127.0.0.1:8000";
input string AgentId = "trusted-agent-001";


void PollCloud()
{
   string url = CloudBaseUrl + "/missions/next";

   char request_body[];
   char response_body[];

   string response_headers;

   ResetLastError();

   int status_code = WebRequest(
      "GET",
      url,
      "",
      3000,
      request_body,
      response_body,
      response_headers
   );

   if(status_code == -1)
   {
      Print(
         "TODOBA Trusted Agent: cloud request failed. error=",
         GetLastError()
      );

      return;
   }


   string response = CharArrayToString(
      response_body
   );


   if(status_code != 200)
   {
      Print(
         "TODOBA Trusted Agent: cloud HTTP status=",
         status_code
      );

      return;
   }


   if(
      StringFind(
         response,
         "\"status\":\"empty\""
      ) >= 0
   )
   {
      Print(
         "TODOBA Trusted Agent: no mission."
      );

      return;
   }


   TODOBAExecutionMission mission;


   if(
      !TODOBAExecutionMissionParser::Parse(
         response,
         mission
      )
   )
   {
      Print(
         "TODOBA Trusted Agent: mission parse rejected."
      );

      return;
   }


   if(
      !TODOBAExecutionMissionValidator::Validate(
         mission,
         AgentId
      )
   )
   {
      Print(
         "TODOBA Trusted Agent: mission rejected. id=",
         mission.mission_id
      );

      return;
   }


   if(
      !TODOBAExecutionPermissionGuard::Allow(
         mission.sequence
      )
   )
   {
      Print(
         "TODOBA Trusted Agent: mission rejected by permission guard. sequence=",
         mission.sequence
      );

      return;
   }


   Print(
      "TODOBA Trusted Agent: mission accepted. id=",
      mission.mission_id,
      " symbol=",
      mission.symbol,
      " type=",
      mission.order_type,
      " volume=",
      DoubleToString(
         mission.volume,
         2
      ),
      " sequence=",
      mission.sequence
   );
}


int OnInit()
{
   if(PollIntervalSeconds < 1)
      return(INIT_PARAMETERS_INCORRECT);

   if(StringLen(CloudBaseUrl) == 0)
      return(INIT_PARAMETERS_INCORRECT);

   if(StringLen(AgentId) == 0)
      return(INIT_PARAMETERS_INCORRECT);


   EventSetTimer(
      PollIntervalSeconds
   );


   Print(
      TODOBA_AGENT_NAME,
      " v",
      TODOBA_AGENT_VERSION,
      " initialized."
   );


   return(INIT_SUCCEEDED);
}


void OnDeinit(const int reason)
{
   EventKillTimer();

   Print(
      TODOBA_AGENT_NAME,
      " stopped. reason=",
      reason
   );
}


void OnTimer()
{
   PollCloud();
}