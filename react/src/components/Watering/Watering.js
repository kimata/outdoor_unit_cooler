import watering_icon from "../../img/watering.png";

const Watering = ({ isReady, ctrlStat }) => {
    const amount = (watering) => {
        return (
            <span className="display-1 align-middle ms-4" data-testid="watering-info">
                <span className="fw-bold watering-value">{watering.toFixed(1)}</span>
                <span className="display-5 ms-2">L</span>
            </span>
        );
    };
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    return (
        <div class="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">本日の散水量</h4>
                    </div>
                    <div className="card-body outdoor_unit">
                        <img src={watering_icon} alt="🚰" width="120px" />
                        {isReady ? amount(ctrlStat.watering) : loading()}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Watering;
