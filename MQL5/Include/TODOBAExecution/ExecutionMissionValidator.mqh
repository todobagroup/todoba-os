#ifndef TODOBA_EXECUTION_MISSION_VALIDATOR_MQH
#define TODOBA_EXECUTION_MISSION_VALIDATOR_MQH

#include <TODOBAExecution/ExecutionMissionParser.mqh>


class TODOBAExecutionMissionValidator
{
public:

   static bool Validate(
      const TODOBAExecutionMission &mission,
      const string expected_agent_id
   )
   {
      if(StringLen(mission.mission_id) == 0)
         return false;

      if(StringLen(mission.agent_id) == 0)
         return false;

      if(mission.agent_id != expected_agent_id)
         return false;

      if(StringLen(mission.account_fingerprint) == 0)
         return false;

      if(StringLen(mission.symbol) == 0)
         return false;

      if(!IsSupportedOrderType(mission.order_type))
         return false;

      if(mission.volume <= 0.0)
         return false;

      if(mission.sl <= 0.0)
         return false;

      if(mission.tp <= 0.0)
         return false;

      if(mission.magic_number <= 0)
         return false;

      if(mission.sequence <= 0)
         return false;

      return true;
   }


private:

   static bool IsSupportedOrderType(
      const string order_type
   )
   {
      return (
         order_type == "BUY" ||
         order_type == "BUY NOW" ||
         order_type == "SELL" ||
         order_type == "SELL NOW" ||
         order_type == "BUY LIMIT" ||
         order_type == "SELL LIMIT" ||
         order_type == "BUY STOP" ||
         order_type == "SELL STOP"
      );
   }
};


#endif