#ifndef TODOBA_CONTROL_MISSION_SIGNING_PAYLOAD_V2_MQH
#define TODOBA_CONTROL_MISSION_SIGNING_PAYLOAD_V2_MQH


#include <TODOBAControl/ControlMissionParserV2.mqh>


class TODOBAControlMissionSigningPayloadV2
{
private:

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
      TODOBAControlMission &mission
   )
   {
      if(mission.security_sequence <= 0)
         return "";

      return (
         Frame(
            "TODOBA_CONTROL_MISSION_V2"
         )
         + Frame(
            mission.mission_id
         )
         + Frame(
            mission.agent_id
         )
         + Frame(
            mission.account_fingerprint
         )
         + Frame(
            mission.action
         )
         + Frame(
            mission.symbol
         )
         + Frame(
            IntegerToString(
               mission.magic_number
            )
         )
         + Frame(
            IntegerToString(
               mission.requested_by_sender_id
            )
         )
         + Frame(
            mission.created_at
         )
         + Frame(
            mission.expires_at
         )
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