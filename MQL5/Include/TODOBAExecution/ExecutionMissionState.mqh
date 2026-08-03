#ifndef TODOBA_EXECUTION_MISSION_STATE_MQH
#define TODOBA_EXECUTION_MISSION_STATE_MQH


enum TODOBAExecutionMissionStateType
{
   RECEIVED = 0,
   ACKNOWLEDGED = 1,
   STARTED = 2,
   COMPLETED = 3,
   FAILED = 4
};


class TODOBAExecutionMissionState
{
private:

   string mission_id;
   string agent_id;
   long sequence;

   TODOBAExecutionMissionStateType state;


public:

   void Initialize(
      const string mission,
      const string agent,
      const long mission_sequence
   )
   {
      mission_id = mission;
      agent_id = agent;
      sequence = mission_sequence;

      state = RECEIVED;
   }


   void Acknowledge()
   {
      state = ACKNOWLEDGED;
   }


   void Start()
   {
      state = STARTED;
   }


   void Complete()
   {
      state = COMPLETED;
   }


   void Fail()
   {
      state = FAILED;
   }


   string MissionId()
   {
      return mission_id;
   }


   string AgentId()
   {
      return agent_id;
   }


   long Sequence()
   {
      return sequence;
   }


   TODOBAExecutionMissionStateType State()
   {
      return state;
   }


   bool IsCompleted()
   {
      return state == COMPLETED;
   }


   bool IsFailed()
   {
      return state == FAILED;
   }

};


#endif