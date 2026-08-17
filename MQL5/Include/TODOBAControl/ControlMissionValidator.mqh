#ifndef TODOBA_CONTROL_MISSION_VALIDATOR_MQH
#define TODOBA_CONTROL_MISSION_VALIDATOR_MQH


#include <TODOBAControl/ControlMissionParser.mqh>
#include <TODOBAExecution/AccountFingerprint.mqh>
#include <TODOBAExecution/MissionFreshnessGuard.mqh>


class TODOBAControlMissionValidator
{
public:

   static bool Validate(
      const TODOBAControlMission &mission,
      const string expected_agent_id,
      const long expected_magic_number
   )
   {
      if(StringLen(mission.mission_id) == 0)
         return false;

      if(StringLen(mission.agent_id) == 0)
         return false;

      if(mission.agent_id != expected_agent_id)
         return false;


      string current_account_fingerprint =
         TODOBAAccountFingerprint::Build();

      if(
         StringLen(
            current_account_fingerprint
         ) == 0
      )
      {
         return false;
      }

      if(
         StringLen(
            mission.account_fingerprint
         ) == 0
      )
      {
         return false;
      }

      if(
         mission.account_fingerprint
         != current_account_fingerprint
      )
      {
         return false;
      }


      if(
         !IsSupportedAction(
            mission.action
         )
      )
      {
         return false;
      }


      if(StringLen(mission.symbol) == 0)
         return false;


      if(expected_magic_number <= 0)
         return false;

      if(mission.magic_number <= 0)
         return false;

      if(
         mission.magic_number
         != expected_magic_number
      )
      {
         return false;
      }


      if(mission.requested_by_sender_id <= 0)
         return false;


      if(
         !TODOBAMissionFreshnessGuard::Validate(
            mission.created_at,
            mission.expires_at
         )
      )
      {
         return false;
      }


      if(mission.sequence <= 0)
         return false;


      return true;
   }


private:

   static bool IsSupportedAction(
      const string action
   )
   {
      return (
         action == "CLOSE_GREEN"
         ||
         action == "CLOSE_RED"
         ||
         action == "CLOSE_BUY"
         ||
         action == "CLOSE_SELL"
         ||
         action == "CLOSE_ALL_POSITIONS"
         ||
         action == "CANCEL_ALL_PENDING"
         ||
         action == "FLATTEN_ALL"
      );
   }
};


#endif