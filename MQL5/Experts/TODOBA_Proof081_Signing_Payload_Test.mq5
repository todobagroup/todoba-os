#property strict

#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionSigningPayload.mqh>
#include <TODOBAExecution/ExecutionMissionSignatureVerifier.mqh>


int OnInit()
{
   TODOBAExecutionMission mission;

   mission.mission_id = "proof081-001";
   mission.agent_id = "trusted-agent-001";
   mission.account_fingerprint = "account-test";
   mission.symbol = "XAUUSD";
   mission.order_type = "BUY";

   mission.volume = 0.01;
   mission.entry = 0.0;
   mission.has_entry = false;

   mission.sl = 4100.0;
   mission.tp = 4200.0;

   mission.magic_number = 10001;
   mission.comment = "TODOBA";

   mission.created_at = "2026-08-08T16:00:00Z";
   mission.expires_at = "2099-01-01T00:00:00Z";

   mission.sequence = 1;

   string payload =
      TODOBAExecutionMissionSigningPayload::Build(
         mission
      );

   string expected_payload =
      "12:proof081-001"
      "17:trusted-agent-001"
      "12:account-test"
      "6:XAUUSD"
      "3:BUY"
      "4:0.01"
      "4:null"
      "4:4100"
      "4:4200"
      "5:10001"
      "6:TODOBA"
      "20:2026-08-08T16:00:00Z"
      "20:2099-01-01T00:00:00Z"
      "1:1";

   if(payload != expected_payload)
   {
      Print(
         "PROOF081 SIGNING PAYLOAD: FAILED"
      );

      return INIT_FAILED;
   }

   string signature = "";

   if(
      !TODOBAExecutionMissionSignatureVerifier::SignForProof(
         mission,
         "proof081-secret",
         signature
      )
   )
   {
      Print(
         "PROOF081 HMAC-SHA256: FAILED TO COMPUTE"
      );

      return INIT_FAILED;
   }

   string expected_signature =
      "5dbd849dc99313deec28bdae720ea7dc"
      "2553b3400d3bc915455a530bafa8a6cd";

   Print(
      "PROOF081 ACTUAL SIGNATURE=[",
      signature,
      "]"
   );

   Print(
      "PROOF081 EXPECTED SIGNATURE=[",
      expected_signature,
      "]"
   );

   if(signature != expected_signature)
   {
      Print(
         "PROOF081 HMAC-SHA256: FAILED"
      );

      return INIT_FAILED;
   }

   if(
      !TODOBAExecutionMissionSignatureVerifier::Verify(
         mission,
         expected_signature,
         "proof081-secret"
      )
   )
   {
      Print(
         "PROOF081 SIGNATURE VERIFY: FAILED"
      );

      return INIT_FAILED;
   }

   Print(
      "PROOF081 SIGNING PAYLOAD: PASSED"
   );

   Print(
      "PROOF081 HMAC-SHA256: PASSED"
   );

   Print(
      "PROOF081 SIGNATURE VERIFY: PASSED"
   );

   return INIT_SUCCEEDED;
}