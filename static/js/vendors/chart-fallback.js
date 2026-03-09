/**
 * Minimal Chart.js Fallback
 * Provides basic chart rendering using Canvas API
 */
(function() {
    'use strict';
    
    window.Chart = function(ctx, config) {
        this.ctx = ctx;
        this.config = config;
        this.canvas = ctx.canvas;
        this.type = config.type;
        this.data = config.data;
        this.options = config.options || {};
        
        this.render();
    };
    
    Chart.defaults = {
        font: {
            family: 'system-ui, -apple-system, sans-serif'
        },
        plugins: {
            legend: {
                position: 'bottom'
            }
        },
        animation: {
            duration: 1000,
            easing: 'easeInOutQuart'
        }
    };
    
    Chart.prototype.render = function() {
        const canvas = this.canvas;
        const ctx = this.ctx;
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        
        if (this.type === 'bar') {
            this.renderBar();
        } else if (this.type === 'line') {
            this.renderLine();
        } else if (this.type === 'pie' || this.type === 'doughnut') {
            this.renderPie();
        }
    };
    
    Chart.prototype.renderBar = function() {
        const ctx = this.ctx;
        const data = this.data;
        const labels = data.labels || [];
        const datasets = data.datasets || [];
        
        if (datasets.length === 0) return;
        
        const canvas = this.canvas;
        const width = canvas.width;
        const height = canvas.height;
        const padding = 40;
        const chartHeight = height - padding * 2;
        const chartWidth = width - padding * 2;
        
        // Find max value
        let maxValue = 0;
        datasets.forEach(dataset => {
            const max = Math.max(...dataset.data);
            if (max > maxValue) maxValue = max;
        });
        
        // Draw bars
        const barWidth = chartWidth / (labels.length * datasets.length + labels.length);
        const groupWidth = barWidth * datasets.length;
        
        datasets.forEach((dataset, datasetIndex) => {
            const color = dataset.backgroundColor || '#4F46E5';
            
            dataset.data.forEach((value, index) => {
                const barHeight = (value / maxValue) * chartHeight;
                const x = padding + index * (groupWidth + barWidth) + datasetIndex * barWidth;
                const y = height - padding - barHeight;
                
                ctx.fillStyle = color;
                ctx.fillRect(x, y, barWidth, barHeight);
            });
        });
        
        // Draw labels
        ctx.fillStyle = '#000';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        labels.forEach((label, index) => {
            const x = padding + index * (groupWidth + barWidth) + groupWidth / 2;
            const y = height - padding + 20;
            ctx.fillText(label, x, y);
        });
    };
    
    Chart.prototype.renderLine = function() {
        const ctx = this.ctx;
        const data = this.data;
        const labels = data.labels || [];
        const datasets = data.datasets || [];
        
        if (datasets.length === 0) return;
        
        const canvas = this.canvas;
        const width = canvas.width;
        const height = canvas.height;
        const padding = 40;
        const chartHeight = height - padding * 2;
        const chartWidth = width - padding * 2;
        
        // Find max value
        let maxValue = 0;
        datasets.forEach(dataset => {
            const max = Math.max(...dataset.data);
            if (max > maxValue) maxValue = max;
        });
        
        const pointSpacing = chartWidth / (labels.length - 1);
        
        datasets.forEach((dataset, datasetIndex) => {
            const color = dataset.borderColor || '#4F46E5';
            
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            dataset.data.forEach((value, index) => {
                const x = padding + index * pointSpacing;
                const y = height - padding - (value / maxValue) * chartHeight;
                
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
                
                // Draw point
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fill();
            });
            
            ctx.stroke();
        });
        
        // Draw labels
        ctx.fillStyle = '#000';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        labels.forEach((label, index) => {
            const x = padding + index * pointSpacing;
            const y = height - padding + 20;
            ctx.fillText(label, x, y);
        });
    };
    
    Chart.prototype.renderPie = function() {
        const ctx = this.ctx;
        const data = this.data;
        const labels = data.labels || [];
        const datasets = data.datasets || [];
        
        if (datasets.length === 0) return;
        
        const canvas = this.canvas;
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 3;
        
        const dataset = datasets[0];
        const total = dataset.data.reduce((sum, val) => sum + val, 0);
        
        let startAngle = -Math.PI / 2;
        
        dataset.data.forEach((value, index) => {
            const sliceAngle = (value / total) * Math.PI * 2;
            const color = dataset.backgroundColor[index] || this.getColor(index);
            
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
            ctx.closePath();
            ctx.fill();
            
            startAngle += sliceAngle;
        });
        
        // Draw legend
        const legendY = height - 40;
        labels.forEach((label, index) => {
            const color = dataset.backgroundColor[index] || this.getColor(index);
            const x = 20 + index * 120;
            
            ctx.fillStyle = color;
            ctx.fillRect(x, legendY, 15, 15);
            
            ctx.fillStyle = '#000';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(label, x + 20, legendY + 12);
        });
    };
    
    Chart.prototype.getColor = function(index) {
        const colors = [
            '#4F46E5', '#10B981', '#F59E0B', '#EF4444', 
            '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
        ];
        return colors[index % colors.length];
    };
    
    Chart.prototype.update = function() {
        this.render();
    };
    
    Chart.prototype.destroy = function() {
        const ctx = this.ctx;
        const canvas = this.canvas;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
})();
