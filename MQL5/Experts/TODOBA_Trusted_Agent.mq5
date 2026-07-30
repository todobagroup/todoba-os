#property strict

#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionValidator.mqh>
#include <TODOBAExecution/ExecutionPermissionGuard.mqh>

#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "0.6.0"

input int PollIntervalSeconds = 5;
input string CloudBaseUrl = "http://127.0.0.1:8000";
input string AgentId = "trusted-agent-001";


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
      "\"status\":\"acknowledged\","
      "\"acknowledged_at\":\"2026-07-29T00:00:00\""
      "}";


   char request_body[];

   StringToCharArray(
      payload,
      request_body
   );


   char response_body[];

   string response_headers;


   int status_code = WebRequest(
      "POST",
      url,
      "Content-Type: application/json\r\n",
      3000,
      request_body,
      response_body,
      response_headers
   );


   if(status_code == -1)
   {
      Print(
         "TODOBA Trusted Agent: acknowledgement failed. error=",
         GetLastError()
      );

      return;
   }


   Print(
      "TODOBA Trusted Agent: acknowledgement sent. mission=",
      mission.mission_id,
      " status=",
      status_code
   );
}



void PollCloud()
{
   string url = CloudBaseUrl + "/missions/next";

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
         "TODOBA Trusted Agent: mission rejected."
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
         "TODOBA Trusted Agent: permission rejected."
      );

      return;
   }


   SendAcknowledgement(
      mission
   );


   Print(
      "TODOBA Trusted Agent: mission accepted. id=",
      mission.mission_id
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
}



void OnTimer()
{
   PollCloud();
}