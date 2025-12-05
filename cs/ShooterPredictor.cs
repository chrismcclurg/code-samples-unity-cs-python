// -------------------------------------------------------------------------------------------------
// ShooterPredictor.cs

// Chris McClurg
// This script communicates with Python ML model to predict the shooter's next positions.
// -------------------------------------------------------------------------------------------------

using System;
using System.Collections;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using System.Collections.Generic;
using System.Linq;

public class ShooterPredictor : MonoBehaviour
{
    // ---------------------------------------------------------------------------------------------
    // Inspector Variables
    // ---------------------------------------------------------------------------------------------

    [Header("Prediction Settings")]
    [Space(5)]
    [ReadOnly, SerializeField] private int timeAhead = 5;       // seconds ahead to predict
    [ReadOnly, SerializeField] private float predictedX;        // predicted x at timeAhead
    [ReadOnly, SerializeField] private float predictedY;        // predicted y at timeAhead
    [ReadOnly, SerializeField] private float predictedZ;        // predicted z at timeAhead

    // ------------------------------------------------------------
    [Header("Scene References")]
    [Space(5)]
    [SerializeField] private GameObject robot1;             // robot on first floor
    [SerializeField] private GameObject robot2;             // robot on second floor
    [SerializeField] private GameObject avatarParent;       // where created npcs are stored
    [SerializeField] private GameObject objectParent;       // where created objects are stored

    // ------------------------------------------------------------
    [Header("Socket Settings")]
    [Space(5)]
    [SerializeField] private  string ipAddress = "127.0.0.1"; // local host
    [SerializeField] private  int rxPort = 8000;            // port to receive data
    [SerializeField] private  int txPort = 8001;            // port to send data

    // ------------------------------------------------------------
    [Header("Visibility Settings")]
    [Space(5)]
    [SerializeField] private float offsetShooterHeight = 2.5f;  // offset for raycasting
    [SerializeField] private float offsetObjHeight = 2.5f;      // offset for raycasting
    [SerializeField] private float offsetProbeMax = 5f;         // offset for raycasting

    // ------------------------------------------------------------
    [Header("Debug Settings")]
    [SerializeField] private bool showPath = false;    // whether to plot path for debugging

    // ---------------------------------------------------------------------------------------------
    // Private Runtime Variables
    // ---------------------------------------------------------------------------------------------

    private List<float> predictedXList = new List<float>();     // predicted x sequence
    private List<float> predictedYList = new List<float>();     // predicted y sequence
    private List<float> predictedZList = new List<float>();     // predicted z sequence

    private GameObject player;                                  // player object

    private List<Transform> dcList = new List<Transform>();     // closed doors
    private List<Transform> doList = new List<Transform>();     // open doors
    private bool doorsIncluded = false;                         // whether to include doors in data

    private float outFreq;                                      // frequency of data output
    private bool isVR;                                          // whether the player is using VR

    private ControlRobot r1;                                    // script attached to robot 1
    private ControlRobot r2;                                    // script attached to robot 2

    private  UdpClient client;                                  // local client
    private  IPEndPoint remoteEndPoint;                         // remote end point for socket
    private  Thread receiveThread;                              // background thread to receive UDP messages
    private bool keepReceiving = true;                          // flag for continuing to send data
    private readonly object predictionLock = new object();

    // ---------------------------------------------------------------------------------------------
    // Main execution
    // ---------------------------------------------------------------------------------------------

    void Awake()
    {
        // create remote endpoint
        remoteEndPoint = new IPEndPoint(IPAddress.Parse(ipAddress), txPort);

        // create local client
        client = new UdpClient(rxPort);

        // create a new thread for reception of incoming messages
        receiveThread = new Thread(new ThreadStart(ReceiveData));
        receiveThread.IsBackground = true;
        receiveThread.Start();
    }

    void Start()
    {
        player = GameObject.FindGameObjectsWithTag("Player")[0];
        isVR = SchoolManager.Instance.IsVR;
        outFreq = GameTimers.Instance.outFreq;
        r1 = robot1.GetComponent<ControlRobot>();
        r2 = robot2.GetComponent<ControlRobot>();
        StartCoroutine(GatherData());
    }

    void Update()
    {
        if (!doorsIncluded && objectParent.transform.childCount > 0)
        {
            foreach (var go in GameObject.FindGameObjectsWithTag("closed_door"))
                dcList.Add(go.transform);

            foreach (var go in GameObject.FindGameObjectsWithTag("open_door"))
                doList.Add(go.transform);

            doorsIncluded = true;
        }
    }

    // ---------------------------------------------------------------------------------------------
    // Helper functions
    // ---------------------------------------------------------------------------------------------

    void OnDisable()
    {
        keepReceiving = false;
        client.Close();
    }

    float round(float input)
    {
        float precision = 0.1f;
        float output = Mathf.Round(input / precision) * precision;
        return output;
    }

    IEnumerator GatherData()
    {
        while (true)
        {
            // player info (gun)
            int nShot = SchoolManager.Instance.shotsFired;
            int nReload = SchoolManager.Instance.reloadsTaken;
            int nDryFire = SchoolManager.Instance.dryFired;
            int nRobotHit = SchoolManager.Instance.robotHit;

            // player info (eyes)
            string focusObject;
            float rightEyeDiam;
            float leftEyeDiam;
            Vector3 focusPos;
            string focusName;
            if (isVR)
            {
                focusObject = CheckFocusObject.Instance.FocusedOn;
                rightEyeDiam = CheckFocusObject.Instance.RD;
                leftEyeDiam = CheckFocusObject.Instance.LD;
            }
            else
            {
                focusObject = "";
                rightEyeDiam = 0.0f;
                leftEyeDiam = 0.0f;
            }

            if (focusObject != "")
            {
                focusPos = CheckFocusObject.Instance.FocusAt;
                focusName = focusObject;
            }

            else
            {
                focusPos = new Vector3(-1f, -1f, -1f);
                focusName = "na";
            }

            // player info (assemble)
            string playerInfo = round(player.transform.position.x) + "," + round(player.transform.position.y) + "," + round(player.transform.position.z);
            playerInfo += ("," + round(player.transform.rotation.eulerAngles.x) + "," + round(player.transform.rotation.eulerAngles.y) + "," + round(player.transform.rotation.eulerAngles.z));
            playerInfo += "," + nShot + "," + nReload + "," + nDryFire + "," + nRobotHit;
            playerInfo += "," + focusName + "," + round(focusPos.x) + "," + round(focusPos.y) + "," + round(focusPos.z) + "," + rightEyeDiam + "," + leftEyeDiam;

            // time info
            float shootTime = GameTimers.Instance.ShootTime;
            float totalTime = GameTimers.Instance.TotalTime;
            string timeInfo = totalTime + "," + shootTime + "," + timeAhead;

            // npc info
            string npcPos = ""; // to be converted into float
            string npcVis = ""; // to be converted into int (visible or not)
            string npcState = ""; // to be converted into int (alive or not)
            foreach (Transform child in avatarParent.transform)
            {
                int tempVisible = CheckVisible(child);
                int tempAlive = (child.gameObject.tag != "dead") ? 1 : 0;
                npcPos += round(child.transform.position.x) + "," + round(child.transform.position.y) + "," + round(child.transform.position.z) + ",";
                npcVis += tempVisible + ",";
                npcState += tempAlive + ",";
            }
            string npcInfo = npcPos + npcVis + npcState;

            // open door info
            string doInfo = ""; // to be converted into int
            foreach (Transform child in doList)
                doInfo += CheckVisible(child) + ",";

            // closed door info
            string dcInfo = ""; // to be converted into int
            foreach (Transform child in dcList)
                dcInfo += CheckVisible(child) + ",";

            // robot info
            string robot1Pos = "";
            string robot2Pos = "";
            int visToR1 = r1.IsShooterVisible ? 1 : 0;
            int visToR2 = r2.IsShooterVisible ? 1 : 0;
            robot1Pos += round(robot1.transform.position.x) + "," + round(robot1.transform.position.y) + "," + round(robot1.transform.position.z);
            robot2Pos += round(robot2.transform.position.x) + "," + round(robot2.transform.position.y) + "," + round(robot2.transform.position.z);
            string robotInfo = "" + visToR1 + "," + visToR2 + "," + robot1Pos + "," + robot2Pos;

            // write info to Python
            string total = timeInfo + ";" + playerInfo + ";" + npcInfo + ";" + doInfo + ";" + dcInfo + ";" + robotInfo;
            SendData(total);

            yield return new WaitForSeconds(1f / outFreq);
        }
    }

    void SendData(string message)
    {
        try
        {
            byte[] data = Encoding.UTF8.GetBytes(message);
            client.Send(data, data.Length, remoteEndPoint);
        }
        catch (Exception err)
        {
            print(err.ToString());
        }
    }

    void ReceiveData()
    {
        while (keepReceiving)
        {
            try
            {
                IPEndPoint anyIP = new IPEndPoint(IPAddress.Any, 0);
                byte[] data = client.Receive(ref anyIP);
                string text = Encoding.UTF8.GetString(data);

                string[] sects = text.Split(";");
                if (sects.Length < 4)
                    continue; // malformed packet

                string[] xStrs = sects[1].Split(",");
                string[] yStrs = sects[2].Split(",");
                string[] zStrs = sects[3].Split(",");

                lock (predictionLock)
                {
                    predictedXList.Clear();
                    predictedYList.Clear();
                    predictedZList.Clear();

                    for (int i = 0; i < xStrs.Length; i++)
                    {
                        predictedXList.Add(float.Parse(xStrs[i]));
                        predictedYList.Add(float.Parse(yStrs[i]));
                        predictedZList.Add(float.Parse(zStrs[i]));
                    }

                    predictedX = predictedXList.Last();
                    predictedY = predictedYList.Last();
                    predictedZ = predictedZList.Last();
                }

                if (showPath)
                {
                    lock (predictionLock)
                    {
                        for (int i = 1; i < predictedXList.Count; i++)
                        {
                            Vector3 pos1 = new Vector3(predictedXList[i - 1], predictedYList[i - 1], predictedZList[i - 1]);
                            Vector3 pos2 = new Vector3(predictedXList[i], predictedYList[i], predictedZList[i]);
                            Debug.DrawLine(pos1, pos2, Color.red, 0.5f, false);
                        }
                    }
                }
            }
            catch (SocketException)
            {
                // Happens when socket is closed — safe to ignore
            }
            catch (Exception err)
            {
                print(err.ToString());
            }
        }
    }


    int CheckVisible(Transform target)
    {
        // shooter position
        Vector3 viewerPos = player.transform.position;
        viewerPos.y += offsetShooterHeight;

        // target position (any object)
        Vector3 targetPos = target.position;
        targetPos.y += offsetObjHeight;

        // direction + distance
        Vector3 dir = (targetPos - viewerPos).normalized;
        float dist = Vector3.Distance(viewerPos, targetPos);

        // probe offset logic
        float probeOffset = (dist > offsetProbeMax)
            ? offsetProbeMax
            : dist * 0.5f;

        Vector3 probePoint = targetPos - dir * probeOffset;

        // linecast
        bool blocked = Physics.Linecast(viewerPos, probePoint);

        return blocked ? 0 : 1;
    }


}
