#property strict

#include <TODOBASecurity/PersistentReplayFloor.mqh>


bool DeleteProofFile(
   const string file_name
)
{
   if(
      !FileIsExist(
         file_name
      )
   )
   {
      return true;
   }

   return FileDelete(
      file_name
   );
}


bool CleanProofState(
   const string file_name
)
{
   if(
      !DeleteProofFile(
         file_name
      )
   )
   {
      return false;
   }

   if(
      !DeleteProofFile(
         file_name
         + ".tmp"
      )
   )
   {
      return false;
   }

   return true;
}


int OnInit()
{
   string execution_file =
      "TODOBA_Proof183_Execution_Replay_Floor.bin";

   string control_file =
      "TODOBA_Proof183_Control_Replay_Floor.bin";

   string agent_id =
      "trusted-agent-001";

   string account_fingerprint =
      "proof183-account";

   string execution_domain =
      "TODOBA_EXECUTION_MISSION_V2";

   string control_domain =
      "TODOBA_CONTROL_MISSION_V2";


   if(
      !CleanProofState(
         execution_file
      )
      ||
      !CleanProofState(
         control_file
      )
   )
   {
      Print(
         "PROOF183 CLEAN STATE: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAPersistentReplayFloor execution_floor;

   if(
      !execution_floor.Configure(
         execution_file,
         execution_domain,
         agent_id,
         account_fingerprint
      )
   )
   {
      Print(
         "PROOF183 EXECUTION CONFIGURE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !execution_floor.Bootstrap(
         41
      )
   )
   {
      Print(
         "PROOF183 EXECUTION BOOTSTRAP: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !execution_floor.IsReady()
      ||
      execution_floor.LastSecuritySequence()
      !=
      41
   )
   {
      Print(
         "PROOF183 EXECUTION INITIAL FLOOR: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      execution_floor.Check(
         41
      )
   )
   {
      Print(
         "PROOF183 EXECUTION REPLAY REJECTION: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !execution_floor.Check(
         42
      )
   )
   {
      Print(
         "PROOF183 EXECUTION NEXT SEQUENCE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !execution_floor.Commit(
         42
      )
   )
   {
      Print(
         "PROOF183 EXECUTION COMMIT: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      execution_floor.LastSecuritySequence()
      !=
      42
   )
   {
      Print(
         "PROOF183 EXECUTION COMMITTED FLOOR: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAPersistentReplayFloor restored_execution_floor;

   if(
      !restored_execution_floor.Configure(
         execution_file,
         execution_domain,
         agent_id,
         account_fingerprint
      )
   )
   {
      Print(
         "PROOF183 EXECUTION RESTORE CONFIGURE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !restored_execution_floor.Restore()
   )
   {
      Print(
         "PROOF183 EXECUTION RESTORE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      restored_execution_floor.LastSecuritySequence()
      !=
      42
   )
   {
      Print(
         "PROOF183 EXECUTION RESTORED FLOOR: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      restored_execution_floor.Check(
         42
      )
   )
   {
      Print(
         "PROOF183 EXECUTION RESTORED REPLAY: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !restored_execution_floor.Check(
         43
      )
   )
   {
      Print(
         "PROOF183 EXECUTION RESTORED NEXT: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAPersistentReplayFloor control_floor;

   if(
      !control_floor.Configure(
         control_file,
         control_domain,
         agent_id,
         account_fingerprint
      )
   )
   {
      Print(
         "PROOF183 CONTROL CONFIGURE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !control_floor.Bootstrap(
         7
      )
   )
   {
      Print(
         "PROOF183 CONTROL BOOTSTRAP: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !control_floor.Commit(
         8
      )
   )
   {
      Print(
         "PROOF183 CONTROL COMMIT: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAPersistentReplayFloor restored_control_floor;

   if(
      !restored_control_floor.Configure(
         control_file,
         control_domain,
         agent_id,
         account_fingerprint
      )
   )
   {
      Print(
         "PROOF183 CONTROL RESTORE CONFIGURE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !restored_control_floor.Restore()
   )
   {
      Print(
         "PROOF183 CONTROL RESTORE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      restored_control_floor.LastSecuritySequence()
      !=
      8
   )
   {
      Print(
         "PROOF183 CONTROL RESTORED FLOOR: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      restored_execution_floor.LastSecuritySequence()
      !=
      42
      ||
      restored_control_floor.LastSecuritySequence()
      !=
      8
   )
   {
      Print(
         "PROOF183 DOMAIN ISOLATION: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAPersistentReplayFloor wrong_domain_floor;

   if(
      !wrong_domain_floor.Configure(
         execution_file,
         control_domain,
         agent_id,
         account_fingerprint
      )
   )
   {
      Print(
         "PROOF183 WRONG DOMAIN CONFIGURE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      wrong_domain_floor.Restore()
   )
   {
      Print(
         "PROOF183 DOMAIN BINDING: FAILED"
      );

      return INIT_FAILED;
   }


   TODOBAPersistentReplayFloor wrong_account_floor;

   if(
      !wrong_account_floor.Configure(
         execution_file,
         execution_domain,
         agent_id,
         "wrong-account"
      )
   )
   {
      Print(
         "PROOF183 WRONG ACCOUNT CONFIGURE: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      wrong_account_floor.Restore()
   )
   {
      Print(
         "PROOF183 ACCOUNT BINDING: FAILED"
      );

      return INIT_FAILED;
   }


   if(
      !CleanProofState(
         execution_file
      )
      ||
      !CleanProofState(
         control_file
      )
   )
   {
      Print(
         "PROOF183 FINAL CLEANUP: FAILED"
      );

      return INIT_FAILED;
   }


   Print(
      "PROOF183 EXECUTION PERSISTENCE: PASSED"
   );

   Print(
      "PROOF183 EXECUTION RESTORE: PASSED"
   );

   Print(
      "PROOF183 REPLAY REJECTION: PASSED"
   );

   Print(
      "PROOF183 EXECUTION CONTROL ISOLATION: PASSED"
   );

   Print(
      "PROOF183 DOMAIN BINDING: PASSED"
   );

   Print(
      "PROOF183 ACCOUNT BINDING: PASSED"
   );

   Print(
      "PROOF183 LOCAL PERSISTENT REPLAY FLOOR: PASSED"
   );

   return INIT_SUCCEEDED;
}