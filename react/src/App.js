import "./App.css";

import "bootstrap/dist/css/bootstrap.min.css";
import { Github } from 'react-bootstrap-icons';
import moment from "moment-timezone";

import { useEffect, useState } from "react";

import preval from 'preval.macro'

import Watering from "./components/Watering/Watering";
import CoolingMode from "./components/CoolingMode/CoolingMode";
import Sensor from "./components/Sensor/Sensor";
import AirConditioner from "./components/AirConditioner/AirConditioner";
import Log from "./components/Log/Log.js";

const App = () => {
    const API_ENDPOINT = "/unit_cooler/api";
    
    const [isStatReady, setStatReady] = useState(false);
    const [isLogReady, setLogReady] = useState(false);
    const [stat, setStat] = useState([]);
    const [log, setLog] = useState([]);
    const [updateTime, setUpdateTime] = useState("Unknown");
    const [error, setError] = useState(false);
    const buildDate = moment(preval`module.exports = new Date().toUTCString();`).format('llll');
    const buildDateFrom = moment(preval`module.exports = new Date().toUTCString();`).fromNow();
    
    useEffect(() => {
        const loadStat = async () => {
            let res = await fetchData(API_ENDPOINT + '/stat');
            setError(false);
            setStat(res);
            setStatReady(true);
            setUpdateTime(moment().format('llll'));
        };
        const loadLog = async () => {
            let res = await fetchData(API_ENDPOINT + '/log_view');
            setError(false);
            setLog(res.data)
            setLogReady(true);
            setUpdateTime(moment().format('llll'));
        };

        let eventSource = null;
        const watchEvent = async () => {
            loadLog();
            eventSource = new EventSource(API_ENDPOINT + '/event');
            eventSource.addEventListener("message", (e) => {
                if (e.data === "log") {
                    loadLog();
                }
            });
            eventSource.onerror = () => {
                if (eventSource.readyState === 2) {
                    eventSource.close();
                    setTimeout(watchEvent, 1000);
                }
            };
        };

        loadStat();
        watchEvent();

        // NOTE: 更新日時表記が，「1分前」になる前に更新を終えれる
        // タイミングで規定する
        const intervalId = setInterval(() => {
            loadStat();
        }, 58000);
        return () => {
            clearInterval(intervalId);
        };
    }, []);

    
    const errorMessage = (message) => {
        return (
            <div className="row justify-content-center" data-testid="error">
                <div className="col-11 text-end">
                    <div class="alert alert-danger d-flex align-items-center" role="alert">
                        <div>{message}</div>
                    </div>
                </div>
            </div>
        );
    };

    const showError = (error) => {
        if (error) {
            return errorMessage("データの読み込みに失敗しました．");
        }
    };

    const fetchData = (url) => {
        return new Promise((resolve, reject) => {
            fetch(url)
                .then((res) => res.json())
                .then((resJson) => resolve(resJson))
                .catch((error) => {
                    setError(true);
                    console.error("通信に失敗しました", error);
                });
        });
    };

    return (
        <div className="App">
            <div className="d-flex flex-column flex-md-row align-items-center p-3 px-md-4 mb-3 bg-white border-bottom shadow-sm">
                <h1 className="display-6 my-0 mr-md-auto font-weight-normal">室外機自動冷却システム</h1>
            </div>
            {showError(error)}
            <div>
                <div className="container">
                    <div className="row display-flex row-cols-1 row-cols-lg-2 row-cols-xl-2 row-cols-xxl-3 g-3">
                        <Watering isReady={isStatReady} stat={stat} />
                        <CoolingMode isReady={isStatReady} stat={stat} />
                        <AirConditioner isReady={isStatReady} stat={stat} />
                        <Sensor isReady={isStatReady} stat={stat} />
                        <Log isReady={isLogReady} log={log} />
                    </div>
                </div>
            </div>
            <div className="p-1 float-end text-end m-2 mt-4">
                <small>
                    <p className="text-muted m-0">
                        <small>更新日時: {updateTime}</small>
                    </p>
                    <p className="text-muted m-0">
                        <small>ビルド日時: { buildDate } [{ buildDateFrom }]</small>
                    </p>
                    <p className="display-6">
                        <a href="https://github.com/kimata/e-ink_weather_panel/" className="text-secondary">
                            <Github />
                        </a>
                    </p>
                </small>
            </div>
        </div>
    );
};

export default App;
