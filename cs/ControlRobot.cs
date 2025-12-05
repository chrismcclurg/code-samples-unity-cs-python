// -------------------------------------------------------------------------------------------------
// ControlRobot.cs

// Chris McClurg
// This script controls robot navigation, visibility logic, distraction behaviors, etc.
// -------------------------------------------------------------------------------------------------

using System;
using TMPro;
using UnityEngine;
using UnityEngine.AI;


public class ControlRobot : MonoBehaviour
{
    // ---------------------------------------------------------------------------------------------
    // Inspector Variables
    // ---------------------------------------------------------------------------------------------
    [Header("Robot State (Read-Only)")]
    [Space(5)]
    [ReadOnly] public string CurrentObjective;              // current robot objective
    [ReadOnly] public bool IsShooterActive;                 // whether shooter is active
    [ReadOnly] public bool IsShooterVisible;                // whether shooter is visible
    [ReadOnly] public float RobotVelocity;                  // robot current velocity

    // ------------------------------------------------------------
    [Header("Movement Settings")]
    [Space(5)]
    [SerializeField] private float robotMaxSpeed = 38.6f;   // [units/s] see speed analysis
    [SerializeField] private float robotRotateSpeed = 3.14f; // [rad/s]
    [SerializeField] private float robotFollowDist = 49.21f; // [units] equal to 5m
    [SerializeField] private float robotStopDist = 4.92f;   // [units] equal to 0.5m
    [SerializeField] private float robotDt = 0.5f;          // [s] how often robot changes objective

    // ------------------------------------------------------------
    [Header("Animation & Audio")]
    [Space(5)]
    [SerializeField] private Animator robotArms;            // animator for arms
    [SerializeField] private Animator robotLight;           // animator for light
    [SerializeField] private AudioSource robotSiren;        // audio source for siren
    [SerializeField] private AudioSource robotWheels;       // audio source for motor
    [SerializeField] private AudioSource robotSpray;        // audio source for spray

    // ------------------------------------------------------------
    [Header("Fog / Smoke Settings")]
    [Space(5)]
    [SerializeField] private GameObject fogPt;              // point at which fog is released
    [SerializeField] private GameObject fogPrefab;          // particle system
    [SerializeField] private GameObject fogParent;          // where to store the fog puffs
    [SerializeField] private int fogSkip = 4;               // only release every N-th timestep
    [SerializeField] private int fogMax = 30;               // max fog objects in the environment

    // ------------------------------------------------------------
    [Header("Visibility Settings")]
    [Space(5)]
    [SerializeField] private float offsetHeight = 2.5f;     // offset for raycasting
    [SerializeField] private float offsetProbeMax = 5f;     // offset for raycasting
    [SerializeField] private float debugRayDuration = 0.1f; // how long to draw ray

    // ------------------------------------------------------------
    [Header("Screen & Lights")]
    [Space(5)]
    [SerializeField] private GameObject screenCalm;         // robot screen during calm mode
    [SerializeField] private GameObject screenAlert;        // robot screen during response
    [SerializeField] private GameObject lightTopOn;         // top light on, else off
    [SerializeField] private GameObject lightFrontOff;      // front light off, else on
    [SerializeField] private GameObject lightRArmOff;       // arm light off, else on
    [SerializeField] private GameObject lightLArmOff;       // arm light off, else on

    // ---------------------------------------------------------------------------------------------
    // Private Runtime Variables
    // ---------------------------------------------------------------------------------------------

    private GameObject player;          // player game object
    private NavMeshAgent navAgent;      // navagent attached to robot

    private Vector3 _targetPos;         // target position of robot
    private float _targetSpeed;         // portion of max speed, 0 to 1
    private float _dt = 0f;             // running time since last step
    private int _fogStep = 0;           // timestep counter for fog emission

    private TMP_Text _txt;              // current text on robot screen

    private bool isVR;                  // whether or not the player is in VR
    private bool isEnabled;             // whether to include robot at all
    private bool isAggressive;          // whether to make robot aggressive (Race else Follow)
    private bool isDistracting;         // whether to include robot light effects
    private bool isFog;                 // whether to include robot smoke effects

    // ---------------------------------------------------------------------------------------------
    // Main execution
    // ---------------------------------------------------------------------------------------------

    void Start()
    {
        isVR = SchoolManager.Instance.IsVR;
        if (!isVR)
        {
            Environment.SetEnvironmentVariable("ROBOT_IS_ENABLED", "1");
            Environment.SetEnvironmentVariable("ROBOT_IS_AGGRESSIVE", "0");
            Environment.SetEnvironmentVariable("ROBOT_IS_DISTRACTING", "1");
            Environment.SetEnvironmentVariable("ROBOT_FOG_ENABLED", "1");

        }
        navAgent = this.GetComponent<NavMeshAgent>();
        isEnabled = (Environment.GetEnvironmentVariable("ROBOT_IS_ENABLED") == "1");
        isAggressive = (Environment.GetEnvironmentVariable("ROBOT_IS_AGGRESSIVE") == "1");
        isDistracting = (Environment.GetEnvironmentVariable("ROBOT_IS_DISTRACTING") == "1");
        isFog = (Environment.GetEnvironmentVariable("ROBOT_FOG_ENABLED") == "1");

        Debug.Log("Robot presence: " + isEnabled);
        Debug.Log("Robot distraction: " + isDistracting);
        Debug.Log("Robot aggressive: " + isAggressive);
        RobotVelocity = 0f;

        IsShooterActive = false;
        IsShooterVisible = false;
        CurrentObjective = "rest";
        robotSiren.mute = true;
        robotSpray.mute = true;

        LightsOFF();
        screenCalm.SetActive(true);
        screenAlert.SetActive(false);

        navAgent.stoppingDistance = robotStopDist;

        if (!isEnabled)
        {
            this.gameObject.SetActive(false);
        }

        if (!isDistracting)
        {
            robotArms.transform.gameObject.SetActive(false);
            robotLight.transform.gameObject.SetActive(false);
            robotSiren.transform.gameObject.SetActive(false);
        }


        player = GameObject.FindGameObjectsWithTag("Player")[0];
        Debug.Log(player);
        UpdateScreenTime();

    }

    // ---------------------------------------------------------------------------------------------

    void Update()
    {
        // check timer
        _dt += Time.deltaTime;

        // update and set objective (if its time)
        if (_dt >= robotDt)
        {
            //reset timer
            _dt = 0f;

            // check if shooter is active
            IsShooterActive = UMA.GameManager.Instance.IsShooterActive;

            // the following logic determines the robot objective
            if (IsShooterActive)
            {

                // use distracting reactors
                ReactorsON();

                // update shooter visibility
                IsShooterVisible = CheckVisible();

                // apply smoke screen (if applicable)
                SmokeScreen();

                // determine objective
                if (IsShooterVisible && isAggressive)   // visible and aggressive
                    CurrentObjective = "race";
                else if (IsShooterVisible)              // visible and not aggresive
                    CurrentObjective = "follow";
                else                                    // not visible
                    CurrentObjective = "search";
            }
            else
            {
                CurrentObjective = "rest";
                UpdateScreenTime();
            }

            // apply objective to navmesh agent
            ApplyObjective(CurrentObjective);
        }

        //look at shooter (if within stopping distance)
        FaceShooter(CurrentObjective);

        // update volumes
        RobotVelocity = navAgent.velocity.magnitude / navAgent.speed;
        robotWheels.volume = RobotVelocity;

    }

    // ---------------------------------------------------------------------------------------------
    // Helper functions
    // ---------------------------------------------------------------------------------------------

    void FaceShooter(string currObj)
    {
        if (currObj != "rest")
        {
            float dist = Vector3.Distance(this.transform.position, navAgent.destination);
            if ((dist < navAgent.stoppingDistance) || (navAgent.pathStatus == NavMeshPathStatus.PathPartial))
            {
                navAgent.updateRotation = false;
                Vector3 direction = (player.transform.position - this.transform.position).normalized;
                Quaternion lookRotation = Quaternion.LookRotation(direction);
                transform.rotation = Quaternion.Slerp(this.transform.rotation, lookRotation, Time.deltaTime * robotRotateSpeed);
            }
        }
    }

    bool CheckVisible()
    {
        // get robot and shooter world positions
        Vector3 robotPos = transform.position;
        Vector3 shooterPos = player.transform.position;
        shooterPos.y += offsetHeight; // offset to eye height

        // get direction and distance from robot to shooter
        Vector3 dirToShooter = (shooterPos - robotPos).normalized;
        float distToShooter = Vector3.Distance(robotPos, shooterPos);

        // get probe point for shooter (not blocked by shooter body or anomalies)
        float probeOffset = (distToShooter > offsetProbeMax)
            ? offsetProbeMax                     // far away, probe 5 units in front
            : distToShooter * 0.5f;              // close, probe halfway
        Vector3 probePoint = shooterPos - dirToShooter * probeOffset;

        // check if something blocks the line between robot and the probe point
        bool blocked = Physics.Linecast(robotPos, probePoint);

        // debug visualization
        Debug.DrawRay(robotPos, probePoint - robotPos,
                    blocked ? Color.red : Color.green,
                    debugRayDuration);

        return !blocked;
    }

    void Toggle(GameObject temp)
    {
        temp.SetActive(!temp.activeSelf);
    }

    void ReactorsON()
    {
        screenCalm.SetActive(false);

        if (isDistracting)
        {
            screenAlert.SetActive(true);
            robotSiren.mute = false;
            robotSiren.Play();
            robotArms.SetTrigger("ShotFired");
            robotLight.SetTrigger("ShotFired");

            lightRArmOff.SetActive(false);
            lightLArmOff.SetActive(false);
            Toggle(lightTopOn);
            Toggle(lightFrontOff);
        }
    }

    void SmokeScreen()
    {
        // play SFX
        if (isFog)
        {
            robotSpray.mute = false;
            robotSpray.Play();
        }

        // increment fog timer
        _fogStep++;

        // only emit fog every Nth step
        if (_fogStep < fogSkip)
            return;

        _fogStep = 0;

        // instantiate fog if shooter visible
        if (isFog && IsShooterVisible)
        {
            GameObject go = Instantiate(fogPrefab, fogPt.transform.position, fogPt.transform.rotation);
            go.transform.parent = fogParent.transform;
        }

        // destroy oldest fog if exceeding max
        if (fogParent.transform.childCount > fogMax)
        {
            Destroy(fogParent.transform.GetChild(0).gameObject);
        }
    }


    void LightsOFF()
    {
        lightTopOn.SetActive(false);
        lightRArmOff.SetActive(true);
        lightLArmOff.SetActive(true);
        lightFrontOff.SetActive(true);
    }

    Vector3 PredictShooterPosition()
    {
        var p = transform.parent.GetComponent<ShooterPredictor>();
        return new Vector3(p.predictedX, p.predictedY, p.predictedZ);
    }

    void ApplyObjective(string currObj)
    {
        //apply objective
        if (currObj == "rest")
        {
            _targetPos = this.transform.position;  //robot current position
            _targetSpeed = 0f;  // portion of max speed
        }
        else if (currObj == "follow")
        {
            _targetPos = player.transform.position + (this.transform.position - player.transform.position).normalized*robotFollowDist;
            _targetSpeed = 1f;  // portion of max speed
        }
        else if (currObj == "race")
        {
            _targetPos = PredictShooterPosition();  // shooter predicted position
            _targetSpeed = 1f;  // portion of max speed

        }

        else if (currObj == "search")
        {
            _targetPos = PredictShooterPosition();  // shooter predicted position
            _targetSpeed = 1f; // portion of max speed

        }
        else
        {
            Debug.Log("Current objective: " + currObj);
            return;
        }

        // set navigation agent
        navAgent.updateRotation = true;
        navAgent.speed = _targetSpeed * robotMaxSpeed;
        navAgent.SetDestination(_targetPos);

    }

    void UpdateScreenTime()
    {
        _txt = screenCalm.transform.GetComponent<TMP_Text>();
        string timeTxt = System.DateTime.Now.ToString("hh:mm tt");
        _txt.text = timeTxt + "\n\n" + "Slightly Cloudy\n" + "74�";
    }


}
