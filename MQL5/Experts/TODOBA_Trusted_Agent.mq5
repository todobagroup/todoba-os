// TODOBA Trusted Agent
// Production Cloud Endpoint Upgrade

#property strict

#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionSignatureVerifier.mqh>
#include <TODOBAExecution/ExecutionMissionValidator.mqh>
#include <TODOBAExecution/ExecutionPermissionGuard.mqh>
#include <TODOBAExecution/ExecutionSafetyGuard.mqh>
#include <TODOBAExecution/BrokerStateReader.mqh>
#include <TODOBAExecution/TODOBAAgentCredentials.mqh>
#include <TODOBAExecution/ExecutionMissionState.mqh>
#include <TODOBAExecution/ExecutionEngine.mqh>
#include <TODOBAExecution/ExecutionResult.mqh>
#include <TODOBAControl/ControlMissionParser.mqh>
#include <TODOBAControl/ControlMissionSignatureVerifier.mqh>
#include <TODOBAControl/ControlMissionValidator.mqh>
#include <TODOBAControl/ControlPermissionGuard.mqh>
#include <TODOBAControl/ControlEngine.mqh>
#include <TODOBAControl/ControlResult.mqh>
#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "1.8.0"
const long TODOBA_MAGIC_NUMBER = 10001;

input int PollIntervalSeconds = 5;

input double MaxSpreadPoints = 100.0;

input int MaxOpenTrades = 10;

input string CloudBaseUrl =
"https://api.todobagroup.com";

input string AgentId =
   "trusted-agent-001";

TODOBAExecutionMissionState current_mission_state;

TODOBAExecutionEngine execution_engine;
TODOBAControlEngine control_engine;
bool IsControlReady()
{
   return (
      StringLen(
         TODOBA_CONTROL_MISSION_SIGNING_SECRET
      ) > 0
   );
}


string BuildAuthenticationHeaders(
   const bool include_content_type
)
{
   string headers =
      "X-TODOBA-Agent-ID: "
      + AgentId
      + "\r\n"
      + "Authorization: Bearer "
      + TODOBA_AGENT_SECRET
      + "\r\n";

   if(include_content_type)
   {
      headers +=
         "Content-Type: application/json\r\n";
   }

   return headers;
}


string UtcNowIso8601()
{
   MqlDateTime value;

   TimeToStruct(
      TimeGMT(),
      value
   );

   return StringFormat(
      "%04d-%02d-%02dT%02d:%02d:%02dZ",
      value.year,
      value.mon,
      value.day,
      value.hour,
      value.min,
      value.sec
   );
}


string EscapeJsonString(
   string value
)
{
   StringReplace(
      value,
      "\\",
      "\\\\"
   );

   StringReplace(
      value,
      "\"",
      "\\\""
   );

   StringReplace(
      value,
      "\r",
      "\\r"
   );

   StringReplace(
      value,
      "\n",
      "\\n"
   );

   StringReplace(
      value,
      "\t",
      "\\t"
   );

   return value;
}


bool PostJson(
   const string endpoint,
   const string payload
)
{
   string url =
      CloudBaseUrl
      + endpoint;

   char request_body[];

   int request_size =
      StringToCharArray(
         payload,
         request_body,
         0,
         WHOLE_ARRAY,
         CP_UTF8
      );

   if(request_size <= 1)
   {
      Print(
         "TODOBA POST payload conversion failed: ",
         endpoint
      );

      return false;
   }

   ArrayResize(
      request_body,
      request_size - 1
   );

   char response_body[];

   string response_headers;

   ResetLastError();

   int status_code =
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

   int error_code =
      GetLastError();

   string response_text =
      CharArrayToString(
         response_body,
         0,
         WHOLE_ARRAY,
         CP_UTF8
      );

   if(status_code != 200)
   {
      Print(
         "TODOBA POST failed: endpoint=",
         endpoint,
         " HTTP=",
         status_code,
         " error=",
         error_code,
         " response=",
         response_text
      );

      return false;
   }

   Print(
      "TODOBA POST succeeded: endpoint=",
      endpoint,
      " HTTP=",
      status_code
   );

   return true;
}

void SendAcknowledgement(
   TODOBAExecutionMission &mission
)
{
   string acknowledged_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"sequence\":"
      + IntegerToString(
         mission.sequence
      )
      + ","
      "\"status\":\"ACCEPTED\","
      "\"acknowledged_at\":\""
      + acknowledged_at
      + "\""
      "}";

   PostJson(
      "/missions/acknowledge",
      payload
   );
}


void SendExecutionStarted(
   TODOBAExecutionMission &mission
)
{
   string started_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"sequence\":"
      + IntegerToString(
         mission.sequence
      )
      + ","
      "\"started_at\":\""
      + started_at
      + "\""
      "}";

   PostJson(
      "/missions/execution_started",
      payload
   );
}
void SendCompleted(
   TODOBAExecutionMission &mission
)
{
   string completed_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"sequence\":"
      + IntegerToString(
         mission.sequence
      )
      + ","
      "\"completed_at\":\""
      + completed_at
      + "\""
      "}";

   if(
      PostJson(
         "/missions/completed",
         payload
      )
   )
   {
      current_mission_state.Complete();
   }
}

void SendFailed(
   TODOBAExecutionMission &mission,
   string reason
)
{
   string failed_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"sequence\":"
      + IntegerToString(
         mission.sequence
      )
      + ","
      "\"failed_at\":\""
      + failed_at
      + "\","
      "\"failure_reason\":\""
      + EscapeJsonString(
         reason
      )
      + "\""
      "}";

   if(
      PostJson(
         "/missions/failed",
         payload
      )
   )
   {
      current_mission_state.Fail();
   }
}

bool SendControlAcknowledgement(
   TODOBAControlMission &mission
)
{
   string acknowledged_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"acknowledged_at\":\""
      + acknowledged_at
      + "\""
      "}";

   return PostJson(
      "/control/missions/acknowledge",
      payload
   );
}


bool SendControlExecutionStarted(
   TODOBAControlMission &mission
)
{
   string started_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"started_at\":\""
      + started_at
      + "\""
      "}";

   return PostJson(
      "/control/missions/execution-started",
      payload
   );
}


bool SendControlCompleted(
   TODOBAControlMission &mission,
   TODOBAControlResult &result
)
{
   string completed_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"completed_at\":\""
      + completed_at
      + "\","
      "\"matched_position_count\":"
      + IntegerToString(
         result.matched_position_count
      )
      + ","
      "\"closed_position_count\":"
      + IntegerToString(
         result.closed_position_count
      )
      + ","
      "\"matched_pending_order_count\":"
      + IntegerToString(
         result.matched_pending_order_count
      )
      + ","
      "\"canceled_pending_order_count\":"
      + IntegerToString(
         result.canceled_pending_order_count
      )
      + "}";

   return PostJson(
      "/control/missions/completed",
      payload
   );
}


bool SendControlFailed(
   TODOBAControlMission &mission,
   TODOBAControlResult &result
)
{
   string failed_at =
      UtcNowIso8601();

   string failure_reason =
      result.failure_reason;

   if(StringLen(failure_reason) == 0)
   {
      failure_reason =
         "Control execution failed.";
   }

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"failed_at\":\""
      + failed_at
      + "\","
      "\"failure_reason\":\""
      + EscapeJsonString(
         failure_reason
      )
      + "\","
      "\"matched_position_count\":"
      + IntegerToString(
         result.matched_position_count
      )
      + ","
      "\"closed_position_count\":"
      + IntegerToString(
         result.closed_position_count
      )
      + ","
      "\"matched_pending_order_count\":"
      + IntegerToString(
         result.matched_pending_order_count
      )
      + ","
      "\"canceled_pending_order_count\":"
      + IntegerToString(
         result.canceled_pending_order_count
      )
      + ","
      "\"failed_item_count\":"
      + IntegerToString(
         result.failed_item_count
      )
      + "}";

   return PostJson(
      "/control/missions/failed",
      payload
   );
}


bool SendBrokerEvidence(
   TODOBAExecutionMission &mission,
   TODOBAExecutionResult &result
)
{
   string completed_at =
      UtcNowIso8601();

   string payload =
      "{"
      "\"mission_id\":\""
      + EscapeJsonString(
         mission.mission_id
      )
      + "\","
      "\"agent_id\":\""
      + EscapeJsonString(
         mission.agent_id
      )
      + "\","
      "\"success\":"
      + (
         result.success
         ? "true"
         : "false"
      )
      + ","
      "\"retcode\":"
      + IntegerToString(
         result.retcode
      )
      + ","
      "\"order_ticket\":"
      + IntegerToString(
         result.order_ticket
      )
      + ","
      "\"deal_ticket\":"
      + IntegerToString(
         result.deal_ticket
      )
      + ","
      "\"execution_price\":"
      + DoubleToString(
         result.price,
         2
      )
      + ","
      "\"comment\":\""
      + EscapeJsonString(
         result.comment
      )
      + "\","
      "\"completed_at\":\""
      + completed_at
      + "\""
      "}";

      return PostJson(
      "/broker/evidence",
      payload
   );
}


void SendBrokerState()
{
   TODOBABrokerState state;

   if(
      !TODOBABrokerStateReader::Read(
         "XAUUSD",
         state
      )
   )
   {
      Print(
         "TODOBA Broker State: read failed."
      );

      return;
   }

   string payload =
      "{"
      "\"account_fingerprint\":\""
      + EscapeJsonString(
         state.account_fingerprint
      )
      + "\","
      "\"equity\":"
      + DoubleToString(
         state.equity,
         2
      )
      + ","
            "\"open_position_count\":"
      + IntegerToString(
         state.open_position_count
      )
      + ","
      "\"pending_order_count\":"
      + IntegerToString(
         state.pending_order_count
      )
      + ","
      "\"symbol\":\""
      + EscapeJsonString(
         state.symbol
      )
      + "\","
      "\"bid\":"
      + DoubleToString(
         state.bid,
         8
      )
      + ","
      "\"ask\":"
      + DoubleToString(
         state.ask,
         8
      )
      + ","
      "\"spread_points\":"
      + DoubleToString(
         state.spread_points,
         2
      )
      + "}";

   bool published =
      PostJson(
         "/broker/state",
         payload
      );

   if(!published)
      return;

   Print(
      "TODOBA Broker State published: ",
      state.account_fingerprint,
      " equity=",
      state.equity,
            " positions=",
      state.open_position_count,
      " pending=",
      state.pending_order_count,
      " spread=",
      state.spread_points
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
   {
      return;
   }

   string mission_signature = "";

   if(
      !TODOBAExecutionMissionParser::ExtractSignature(
         response,
         mission_signature
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " rejected mission=",
         mission.mission_id,
         " reason=missing signature"
      );

      return;
   }

   if(
      !TODOBAExecutionMissionSignatureVerifier::Verify(
         mission,
         mission_signature,
         TODOBA_MISSION_SIGNING_SECRET
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " rejected mission=",
         mission.mission_id,
         " reason=invalid signature"
      );

      return;
   }

   Print(
      TODOBA_AGENT_NAME,
      " verified mission=",
      mission.mission_id
   );

   if(
      !TODOBAExecutionMissionValidator::Validate(
         mission,
         AgentId
      )
   )
   {
      return;
   }

   if(
      !TODOBAExecutionPermissionGuard::Allow(
         mission.sequence
      )
   )
   {
      return;
   }

   current_mission_state.Initialize(
   mission.mission_id,
   mission.agent_id,
   mission.sequence
);

string safety_reason = "";

if(
   !TODOBAExecutionSafetyGuard::Allow(
      mission.symbol,
      MaxSpreadPoints,
      MaxOpenTrades,
      safety_reason
   )
)
{
   Print(
      "TODOBA SAFETY REJECTED: ",
      safety_reason
   );

   SendFailed(
      mission,
      safety_reason
   );

   return;
}

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

      if(execution_result.success)
   {
      bool evidence_stored =
         SendBrokerEvidence(
            mission,
            execution_result
         );

      if(evidence_stored)
      {
         SendCompleted(
            mission
         );
      }
      else
      {
         Print(
            "TODOBA CRITICAL: broker execution succeeded "
            "but evidence was not stored."
         );
      }
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

void PollControlCloud()
{
   if(
      !IsControlReady()
   )
   {
      return;
   }


   string url =
      CloudBaseUrl
      + "/control/missions/next";

   char request_body[];
   char response_body[];

   string response_headers;


   long status_code =
      WebRequest(
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


   TODOBAControlMission mission;


   if(
      !TODOBAControlMissionParser::Parse(
         response,
         mission
      )
   )
   {
      return;
   }


   string mission_signature = "";


   if(
      !TODOBAControlMissionParser::ExtractSignature(
         response,
         mission_signature
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " rejected control mission=",
         mission.mission_id,
         " reason=missing signature"
      );

      return;
   }


   if(
      !TODOBAControlMissionSignatureVerifier::Verify(
         mission,
         mission_signature,
         TODOBA_CONTROL_MISSION_SIGNING_SECRET
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " rejected control mission=",
         mission.mission_id,
         " reason=invalid signature"
      );

      return;
   }


   if(
      !TODOBAControlMissionValidator::Validate(
         mission,
         AgentId,
         TODOBA_MAGIC_NUMBER
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " rejected control mission=",
         mission.mission_id,
         " reason=validation failed"
      );

      return;
   }


   if(
      !TODOBAControlPermissionGuard::Check(
         mission.sequence
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " rejected control mission=",
         mission.mission_id,
         " reason=sequence rejected"
      );

      return;
   }


   if(
      !SendControlAcknowledgement(
         mission
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " control mission ACK failed=",
         mission.mission_id
      );

      return;
   }


   if(
      !TODOBAControlPermissionGuard::Commit(
         mission.sequence
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " control mission sequence commit failed=",
         mission.mission_id
      );

      return;
   }


   if(
      !SendControlExecutionStarted(
         mission
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " control mission start evidence failed=",
         mission.mission_id
      );

      return;
   }


   Print(
      TODOBA_AGENT_NAME,
      " executing control mission=",
      mission.mission_id,
      " action=",
      mission.action,
      " symbol=",
      mission.symbol,
      " magic=",
      mission.magic_number
   );


   TODOBAControlResult control_result =
      control_engine.Execute(
         mission
      );


   Print(
      "TODOBA Control Result: success=",
      control_result.success,
      " matched_positions=",
      control_result.matched_position_count,
      " closed_positions=",
      control_result.closed_position_count,
      " matched_pending=",
      control_result.matched_pending_order_count,
      " canceled_pending=",
      control_result.canceled_pending_order_count,
      " failed_items=",
      control_result.failed_item_count,
      " reason=",
      control_result.failure_reason
   );


   if(control_result.success)
   {
      if(
         !SendControlCompleted(
            mission,
            control_result
         )
      )
      {
         Print(
            "TODOBA CRITICAL: control broker action succeeded "
            "but completion evidence was not stored. mission=",
            mission.mission_id
         );
      }
   }
   else
   {
      if(
         !SendControlFailed(
            mission,
            control_result
         )
      )
      {
         Print(
            "TODOBA CRITICAL: control execution failed "
            "but failure evidence was not stored. mission=",
            mission.mission_id
         );
      }
   }


   Print(
      TODOBA_AGENT_NAME,
      " finished control mission=",
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

      if(StringLen(TODOBA_AGENT_SECRET) == 0)
      return INIT_PARAMETERS_INCORRECT;

      if(StringLen(TODOBA_MISSION_SIGNING_SECRET) == 0)
      return INIT_PARAMETERS_INCORRECT;
      
   if(
      !IsControlReady()
)
{
      Print(
         TODOBA_AGENT_NAME,
          " control standby: signing secret not configured."
   );
}

   if(
      !TerminalInfoInteger(
         TERMINAL_VPS
      )
   )
   {
      Print(
         TODOBA_AGENT_NAME,
         " local standby: MetaTrader VPS required."
      );

      return INIT_SUCCEEDED;
   }

   Print(
      "TODOBA Agent Credential DEBUG: AgentId=",
      AgentId,
      " AgentSecretLength=",
      StringLen(TODOBA_AGENT_SECRET)
   );
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
   SendBrokerState();

   PollCloud();

   PollControlCloud();
}