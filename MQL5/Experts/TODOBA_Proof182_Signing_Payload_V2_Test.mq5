#property strict

#include <TODOBAExecution/ExecutionMissionParserV2.mqh>
#include <TODOBAExecution/ExecutionMissionSigningPayloadV2.mqh>
#include <TODOBAExecution/ExecutionMissionSignatureVerifierV2.mqh>


int OnInit()
{
   TODOBAExecutionMission mission;

   mission.mission_id = "proof182-001";
   mission.agent_id = "trusted-agent-001";
   mission.account_fingerprint = "account-test";
   mission.symbol = "XAUUSD";
   mission.order_type = "BUY LIMIT";

   mission.volume = 0.05;
   mission.entry = 4099.5;
   mission.has_entry = true;

   mission.sl = 4080.0;
   mission.tp = 4150.0;

   mission.magic_number = 10001;
   mission.comment = "TODOBA|V2";

   mission.created_at = "2026-08-18T02:00:00Z";
   mission.expires_at = "2099-01-01T00:00:00Z";

   mission.sequence = 168001;
   mission.security_sequence = 42;

   string payload =
      TODOBAExecutionMissionSigningPayloadV2::Build(
         mission
      );

   string expected_payload =
      "27:TODOBA_EXECUTION_MISSION_V2"
      "12:proof182-001"
      "17:trusted-agent-001"
      "12:account-test"
      "6:XAUUSD"
      "9:BUY LIMIT"
      "4:0.05"
      "6:4099.5"
      "4:4080"
      "4:4150"
      "5:10001"
      "9:TODOBA|V2"
      "20:2026-08-18T02:00:00Z"
      "20:2099-01-01T00:00:00Z"
      "6:168001"
      "2:42";

   if(payload != expected_payload)
   {
      Print(
         "PROOF182 V2 SIGNING PAYLOAD: FAILED"
      );

      Print(
         "ACTUAL=[",
         payload,
         "]"
      );

      Print(
         "EXPECTED=[",
         expected_payload,
         "]"
      );

      return INIT_FAILED;
   }

   string signature = "";

   if(
      !TODOBAExecutionMissionSignatureVerifierV2::SignForProof(
         mission,
         "proof182-secret",
         signature
      )
   )
   {
      Print(
         "PROOF182 V2 HMAC-SHA256: "
         "FAILED TO COMPUTE"
      );

      return INIT_FAILED;
   }

   string expected_signature =
      "d264045fb230dfc316ad6b8c50228b36"
      "c1043753360ef46c9805efab1da57a0d";

   Print(
      "PROOF182 V2 ACTUAL SIGNATURE=[",
      signature,
      "]"
   );

   Print(
      "PROOF182 V2 EXPECTED SIGNATURE=[",
      expected_signature,
      "]"
   );

   if(signature != expected_signature)
   {
      Print(
         "PROOF182 V2 HMAC-SHA256: FAILED"
      );

      return INIT_FAILED;
   }

   if(
      !TODOBAExecutionMissionSignatureVerifierV2::Verify(
         mission,
         expected_signature,
         "proof182-secret"
      )
   )
   {
      Print(
         "PROOF182 V2 SIGNATURE VERIFY: FAILED"
      );

      return INIT_FAILED;
   }

   mission.security_sequence = 43;

   if(
      TODOBAExecutionMissionSignatureVerifierV2::Verify(
         mission,
         expected_signature,
         "proof182-secret"
      )
   )
   {
      Print(
         "PROOF182 V2 REPLAY BINDING: FAILED"
      );

      return INIT_FAILED;
   }

   Print(
      "PROOF182 V2 SIGNING PAYLOAD: PASSED"
   );

   Print(
      "PROOF182 V2 HMAC-SHA256: PASSED"
   );

   Print(
      "PROOF182 V2 SIGNATURE VERIFY: PASSED"
   );

   Print(
      "PROOF182 V2 SECURITY SEQUENCE BINDING: PASSED"
   );

   return INIT_SUCCEEDED;
}