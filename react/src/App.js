import './App.css';

import 'bootstrap/dist/css/bootstrap.min.css';
import moment from 'moment-timezone';

import { useEffect, useState } from "react";
import Watering from "./components/Watering/Watering";
import CoolingMode from "./components/CoolingMode/CoolingMode";
import Sensor from "./components/Sensor/Sensor";
import AirConditioner from "./components/AirConditioner/AirConditioner";

const App = () => {
    const API_ENDPOINT = "http://192.168.0.10:5000/unit_cooler/api/stat";
    const [isReady, setReady] = useState(false);
    const [ctrlStat, setCtrlStat] = useState([]);
    const [updateTime, setUpdateTime] = useState("Unknown");
    const [error, setError] = useState(false);
    
    useEffect(() => {
        const loadCtrlStat = async () => {
            let res = await fetchCtrlStat(API_ENDPOINT);
            setError(false);
            setCtrlStat(res);
            setReady(true);
            setUpdateTime(moment().format('YYYY-MM-DD HH:mm:ss'));
        };
        loadCtrlStat();

        const intervalId = setInterval(() => {
            loadCtrlStat();
        }, 10000);
        return () => {
            clearInterval(intervalId);
        };
    }, []);


    const errorMessage = (error) => {
        if (error) {
            return (
            <div className="row justify-content-center">
                <div className="col-10 text-end">
                    <div class="alert alert-danger d-flex align-items-center" role="alert">
                        <div>
                            データの読み込みに失敗しました．
                        </div>
                    </div>
                </div>
            </div>
            )
        }
    }
    
    const fetchCtrlStat = (url) => {
        return new Promise((resolve, reject) => {
            fetch(url)
                .then((res) => res.json())
                .then((resJson) => resolve(resJson))
                .catch(error => {
                    setError(true);
                    console.error('通信に失敗しました', error);
                });
        });
    };
    
    return (
        <div className="App">
            <div className="d-flex flex-column flex-md-row align-items-center p-3 px-md-4 mb-3 bg-white border-bottom shadow-sm">
                <h5 className="display-6 my-0 mr-md-auto font-weight-normal">エアコン室外機冷却システム</h5>
            </div>
            { errorMessage(error) }
            <Watering isReady={isReady} ctrlStat={ctrlStat} />
            <CoolingMode isReady={isReady} ctrlStat={ctrlStat} />
            <AirConditioner isReady={isReady} ctrlStat={ctrlStat} />
            <Sensor isReady={isReady} ctrlStat={ctrlStat} />
            <div className="row justify-content-center">
                <div className="col-9 text-end">Last modified: {updateTime}</div>
            </div>
        </div>
  );
}

export default App;
