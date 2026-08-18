#ifndef TODOBA_EXECUTION_MISSION_SIGNING_PAYLOAD_V2_MQH
#define TODOBA_EXECUTION_MISSION_SIGNING_PAYLOAD_V2_MQH


#include <TODOBAExecution/ExecutionMissionParserV2.mqh>


class TODOBAExecutionMissionSigningPayloadV2
{
private:

   static string NormalizeNumber(
      const double value
   )
   {
      string normalized = DoubleToString(
         value,
         8
      );

      while(
         StringLen(normalized) > 0 &&
         StringSubstr(
            normalized,
            StringLen(normalized) - 1,
            1
         ) == "0"
      )
      {
         normalized = StringSubstr(
            normalized,
            0,
            StringLen(normalized) - 1
         );
      }

      if(
         StringLen(normalized) > 0 &&
         StringSubstr(
            normalized,
            StringLen(normalized) - 1,
            1
         ) == "."
      )
      {
         normalized = StringSubstr(
            normalized,
            0,
            StringLen(normalized) - 1
         );
      }

      if(
         normalized == "-0" ||
         normalized == ""
      )
      {
         return "0";
      }

      return normalized;
   }


   static int Utf8Length(
      const string value
   )
   {
      uchar bytes[];

      int copied = StringToCharArray(
         value,
         bytes,
         0,
         WHOLE_ARRAY,
         CP_UTF8
      );

      if(copied <= 0)
         return 0;

      return copied - 1;
   }


   static string Frame(
      const string value
   )
   {
      return (
         IntegerToString(
            Utf8Length(value)
         )
         + ":"
         + value
      );
   }


public:

   static string Build(
      TODOBAExecutionMission &mission
   )
   {
      if(mission.security_sequence <= 0)
         return "";

      string entry_value = "null";

      if(mission.has_entry)
      {
         entry_value = NormalizeNumber(
            mission.entry
         );
      }

      return (
         Frame(
            "TODOBA_EXECUTION_MISSION_V2"
         )
         + Frame(mission.mission_id)
         + Frame(mission.agent_id)
         + Frame(mission.account_fingerprint)
         + Frame(mission.symbol)
         + Frame(mission.order_type)
         + Frame(
            NormalizeNumber(
               mission.volume
            )
         )
         + Frame(entry_value)
         + Frame(
            NormalizeNumber(
               mission.sl
            )
         )
         + Frame(
            NormalizeNumber(
               mission.tp
            )
         )
         + Frame(
            IntegerToString(
               mission.magic_number
            )
         )
         + Frame(mission.comment)
         + Frame(mission.created_at)
         + Frame(mission.expires_at)
         + Frame(
            IntegerToString(
               mission.sequence
            )
         )
         + Frame(
            IntegerToString(
               mission.security_sequence
            )
         )
      );
   }
};


#endif