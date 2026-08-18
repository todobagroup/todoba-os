#property strict

#include <TODOBAExecution/AccountFingerprint.mqh>
#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionValidator.mqh>


TODOBAExecutionMission BuildValidMission(
   const string account_fingerprint
)
{
   TODOBAExecutionMission mission;

   mission.mission_id = "proof184-001";
   mission.agent_id = "trusted-agent-001";
   mission.account_fingerprint = account_fingerprint;

   mission.symbol = "XAUUSD";
   mission.order_type = "BUY";

   mission.volume = 0.01;
   mission.entry = 0.0;
   mission.has_entry = false;

   mission.sl = 4000.0;
   mission.tp = 4200.0;

   mission.magic_number = 10001;
   mission.comment = "TODOBA|PROOF184";

   mission.created_at = "2026-08-18T00:00:00Z";
   mission.expires_at = "2099-01-01T00:00:00Z";

   mission.sequence = 184001;
   mission.security_sequence = 0;

   return mission;
}


int OnInit()
{
   string current_account_fingerprint =
      TODOBAAccountFingerprint::Build();

   if(
      StringLen(
         current_account_fingerprint
      ) == 0
   )
   {
      Print(
         "PROOF184 CURRENT ACCOUNT FINGERPRINT: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAExecutionMission correct_mission =
      BuildValidMission(
         current_account_fingerprint
      );

   if(
      !TODOBAExecutionMissionValidator::Validate(
         correct_mission,
         "trusted-agent-001"
      )
   )
   {
      Print(
         "PROOF184 CORRECT ACCOUNT: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAExecutionMission wrong_account_mission =
      BuildValidMission(
         current_account_fingerprint
         + "-WRONG"
      );

   if(
      TODOBAExecutionMissionValidator::Validate(
         wrong_account_mission,
         "trusted-agent-001"
      )
   )
   {
      Print(
         "PROOF184 WRONG ACCOUNT REJECTION: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAExecutionMission empty_account_mission =
      BuildValidMission(
         ""
      );

   if(
      TODOBAExecutionMissionValidator::Validate(
         empty_account_mission,
         "trusted-agent-001"
      )
   )
   {
      Print(
         "PROOF184 EMPTY ACCOUNT REJECTION: FAILED"
      );

      return INIT_FAILED;
   }


   Print(
      "PROOF184 CURRENT ACCOUNT FINGERPRINT: PASSED"
   );

   Print(
      "PROOF184 CORRECT ACCOUNT: PASSED"
   );

   Print(
      "PROOF184 WRONG ACCOUNT REJECTION: PASSED"
   );

   Print(
      "PROOF184 EMPTY ACCOUNT REJECTION: PASSED"
   );

   return INIT_SUCCEEDED;
}