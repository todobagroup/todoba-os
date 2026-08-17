#ifndef TODOBA_CONTROL_MISSION_SIGNING_PAYLOAD_MQH
#define TODOBA_CONTROL_MISSION_SIGNING_PAYLOAD_MQH


#include <TODOBAControl/ControlMissionParser.mqh>


class TODOBAControlMissionSigningPayload
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
      return (
         Frame(
            "TODOBA_CONTROL_MISSION_V1"
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
      );
   }
};


#endif