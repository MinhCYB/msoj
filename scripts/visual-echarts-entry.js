import * as echarts from 'echarts/core';
import {BarChart, LineChart, ScatterChart} from 'echarts/charts';
import {GridComponent, TooltipComponent, LegendComponent, AriaComponent} from 'echarts/components';
import {SVGRenderer} from 'echarts/renderers';

echarts.use([BarChart, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, SVGRenderer]);
window.echarts = echarts;
